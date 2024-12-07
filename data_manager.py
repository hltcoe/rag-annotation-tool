from typing import Iterable, Set, Tuple, List, Dict, Literal, Mapping, Union
from pathlib import Path

import streamlit as st

import sqlite3
import pandas as pd

import json
from copy import deepcopy

from task_resources import TaskConfig


class SqliteManager:

    def __init__(self, db_path: str, persistent_connection: bool = True):
        self.db_path = str(db_path)
        self.persistent_connection = persistent_connection

        self._conn = None
    
    @property
    def conn(self):
        if self.persistent_connection:
            if self._conn is None:
                self._conn = sqlite3.connect(self.db_path)
            return self._conn
        return sqlite3.connect(self.db_path)

    def table_exists(self, table_name: str):
        return len(self.execute_simple(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")) > 0

    def execute_simple(self, query: str, args = None, query_only: bool = None, conn: sqlite3.Connection=None):
        if conn is None:
            conn = self.conn

        if query_only is None:
            query_only = query.lower().startswith('select')

        try:
            query = query.strip()
            if args:
                cursor = conn.execute(query, args)
            else:
                cursor = conn.execute(query)

            if query_only:
                return cursor.fetchall()
            
            conn.commit()
        except sqlite3.OperationalError:
            st.error("Database error. Try again later.")


class ActivityLogMananger(SqliteManager):

    def __init__(self, db_path: str, username: str):
        super().__init__(db_path, persistent_connection=False)
        self.username = username

        if not self.table_exists('log'):
            self.execute_simple("""create table if not exists logs (username string, query string, args string, ts datetime default current_timestamp);""")
    
    def log(self, query: str, args = None):
        query = query.strip()

        print("[LOG] ", query.replace("\n", '  '), args)

        if args is not None:
            args = json.dumps(args)
            self.execute_simple("""insert into logs (username, query, args) values (?, ?, ?)""", (self.username, query, args))
        else:
            self.execute_simple("""insert into logs (username, query) values (?, ?)""", (self.username, query))
        


class NuggetSet:

    def __init__(self):
        self.nugget_list: List[Tuple[str, Dict[str, Set[str]]]] = []
        # [ (question, { answer: {doc_id...} ... }), ... ]
        self.group_assignment: Dict[str, str] = {}
        # {question: group}

    def get(self, question: str, default=None, only_answers: bool=False):
        question = question.strip()
        for q, a_dict in self.nugget_list:
            if q == question:
                return a_dict if not only_answers else a_dict.keys()
            
        return default

    @property
    def groups(self):
        return sorted(set(self.group_assignment.values())) + ["default"]

    def __contains__(self, key: str):
        return self.get(key) is not None

    def __getitem__(self, idx: int):
        return self.nugget_list[idx]

    def set_group(self, nq: str, group: str):
        assert nq in self
        assert group is not None
        if group == "default":
            del self.group_assignment[nq]
        else:
            self.group_assignment[nq] = group

    def get_group(self, nq: str):
        return self.group_assignment.get(nq, "default")

    def rename_group(self, old_name: str, new_name: str):
        assert old_name in self.groups and old_name != "default" and new_name != "default"
        self.group_assignment = {
            nq: gp if gp != old_name else new_name
            for nq, gp in self.group_assignment.items()
        }

    def iter_grouped_nuggets(self):
        inverted_group = { g: [] for g in self.groups }
        for idx, (nq, a_dict) in enumerate(self.nugget_list):
            if nq in self.group_assignment:
                inverted_group[self.group_assignment[nq]].append((idx, nq, a_dict))
        inverted_group['default'] = [ 
            (idx, nq, a_dict)
            for idx, (nq, a_dict) in enumerate(self.nugget_list) 
            if nq not in self.group_assignment 
        ]

        for group in self.groups: # sort by group name
            yield group, sorted(inverted_group[group], key=lambda x: x[1]) # sort by question


    def iter_nuggets(self, only_answers: bool=False):
        yield from (
            (nidx, question, a_dict.keys() if only_answers else a_dict)
            for nidx, (question, a_dict) in enumerate(self.nugget_list)
        )

    def add(self, question: str, doc_answer_pairs: Iterable[Tuple[str, str]]):
        question = question.strip()
        # doc_answer_pairs = [ (d, a.strip()) for d, a in doc_answer_pairs ]
        answer_new_dict: Dict[str, Set[str]] = {}
        for doc_id, answer in doc_answer_pairs:
            if answer not in answer_new_dict:
                answer_new_dict[answer] = set()
            answer_new_dict[answer].add(doc_id)
            

        if question in self:
            for answer, doc_set in answer_new_dict.items():
                existing_answer_dict = self.get(question)
                if answer in existing_answer_dict:
                    existing_answer_dict[answer] |= doc_set
                else:
                    existing_answer_dict[answer] = doc_set
        
        else:
            self.nugget_list.append(
                (question, answer_new_dict)
            )
    
    def remove(self, question: str, doc_id: str, answers: List[str]):
        assert question in self
        for answer in answers:
            assert answer in self.get(question)
            assert doc_id in self.get(question)[answer]
            
            self.get(question)[answer].remove(doc_id)

    def __add__(self, obj: 'NuggetSet'):
        new_nugget_set = self.__class__()
        new_nugget_set.nugget_list = deepcopy(self.nugget_list)

        for q, a_dict in obj.nugget_list:
            if q in new_nugget_set:
                for answer, doc_set in a_dict.items():
                    if answer in self.get(q):
                        new_nugget_set.get(q)[answer] |= doc_set
                    else:
                        new_nugget_set.get(q)[answer] = doc_set
            else:
                new_nugget_set.nugget_list.append((q, a_dict))

        new_nugget_set.group_assignment = { **self.group_assignment, **obj.group_assignment }
        
        return new_nugget_set

    def as_nugget_dict(self, only_answers: bool = False):
        return {
            q: sorted(a_dict.keys()) if only_answers else a_dict
            for q, a_dict in self.nugget_list
        }

    def as_json(self, indent=None):
        return json.dumps({
            'nugget_dict': {
                q: { a: list(doc_set) for a, doc_set in a_dict.items() }
                for q, a_dict in self.as_nugget_dict(only_answers=False).items()
            },
            'group_assignment': {
                nq: gp
                for nq, gp in self.group_assignment.items() if gp != "default"
            }
        }, indent=indent)

    def as_dataframe(self):
        return pd.DataFrame({
            'Question': [ q for q, _ in self.nugget_list ],
            'Answers': [ "; ".join(sorted(a_dict.keys())) for _, a_dict in self.nugget_list ]
        }).astype(str)

    @classmethod
    def from_dict(cls, nugget_dict: Dict[str, Dict[str, List[str]]], group_assignment: Dict[str, str] = {}):
        ret = cls()
        ret.nugget_list = [
            (question, { answer: set(doc_ids) for answer, doc_ids in a_dict.items() })
            for question, a_dict in nugget_dict.items()
        ]

        assert len(group_assignment.keys() - nugget_dict.keys()) == 0
        ret.group_assignment = group_assignment
        
        return ret

    @classmethod
    def from_json(cls, json_string: str):
        json_dict = json.loads(json_string)
        if "nugget_dict" not in json_dict:
            json_dict = {"nugget_dict": json_dict}
        return cls.from_dict(**json_dict)


class NuggetSelection(set):

    def __init__(self, selections: Set[Tuple[str, str]] = None):
        super().__init__(selections or [])
    
    @classmethod
    def from_json(cls, json_string: str):
        if json_string is None:
            return cls()
        return cls(map(tuple, json.loads(json_string)))
    
    def as_json(self):
        return json.dumps(sorted(self))

    def as_dataframe(self):
        return pd.DataFrame(sorted(self), columns=['Question', 'Answer'])


class NuggetViewer(SqliteManager):

    def __init__(
            self, 
            username: str,
            db_path: str = None, load_dir: str = None, 
            use_json: bool=True, 
            combine_nuggets_from_multiple_users: bool=True,
            use_revised_nugget_only: bool=True
        ):
        assert (db_path is not None) or (load_dir is not None)
        if use_json:
            assert load_dir is not None

        super().__init__(db_path, persistent_connection=False)
        self.load_dir = Path(load_dir)

        self.username = username
        self.use_json = use_json
        self.combine_nuggets_from_multiple_users = combine_nuggets_from_multiple_users
        self.use_revised_nugget_only = use_revised_nugget_only
    
    def iter_nugget_sets_from_json(self, topic_id: str):
        if self.use_revised_nugget_only:
            fns = self.load_dir.glob(f"nuggets_{topic_id}.revised.json")
        else:
            fns = self.load_dir.glob(f"nuggets_{topic_id}_{"*" if self.combine_nuggets_from_multiple_users else self.username}.json")

        yield from map(lambda fn: NuggetSet.from_json(fn.read_text()), fns)
        
    def iter_nuggest_sets_from_db(self, topic_id: str):
        if not self.combine_nuggets_from_multiple_users:
            records = self.execute_simple(
                """select nugget_json from nuggets where topic_id = ? and username = ?;""", 
                (topic_id, self.username)
            )
        else:
            records = self.execute_simple(
                """select nugget_json from nuggets where topic_id = ?;""", (topic_id, )
            )

        yield from map(NuggetSet.from_json, records)
        
    def __getitem__(self, topic_id: str):
        return sum(
            (self.iter_nugget_sets_from_json if self.use_json else self.iter_nuggest_sets_from_db)(topic_id),
            NuggetSet()
        )


class NuggetSaverManager(SqliteManager):

    def __init__(self, db_path: str, output_dir: str, log_manager: ActivityLogMananger):
        super().__init__(db_path, persistent_connection=False)
        self.logger = log_manager
        self.username = self.logger.username
        self.output_dir = Path(output_dir)

        self.topic_nuggets: Dict[str, NuggetSet] = {}

        if not self.table_exists('nuggets'):
            self.execute_simple("""
                create table if not exists nuggets (
                    username string, topic_id string, 
                    nugget_json string, ts datetime default current_timestamp
                );
            """)

        existing_nugget_records = self.execute_simple("""select topic_id, nugget_json from nuggets;""")
        # print(existing_nugget_records)
        for topic_id, nugget_json in existing_nugget_records:
            self.topic_nuggets[str(topic_id)] = NuggetSet.from_json(nugget_json)

        for fn in self.output_dir.glob("nuggets_*.preload.json"):
            topic_id = fn.stem.replace(".preload", "").split("_", 2)[1]
            if topic_id not in self.topic_nuggets:
                self.topic_nuggets[topic_id] = NuggetSet.from_json(fn.read_text())
        
    def __getitem__(self, topic_id: str):
        if topic_id not in self.topic_nuggets:
            self.topic_nuggets[topic_id] = NuggetSet()

        return self.topic_nuggets[topic_id]

    def __contains__(self, topic_id: str):
        return topic_id in self.topic_nuggets

    def flush(self, topic_id: str):
        assert topic_id in self 

        sql_query, sql_args = f"""
            insert or replace into nuggets (rowid, username, topic_id, nugget_json) values (
            (select rowid from nuggets where topic_id = "{topic_id}"), ?, ?, json(?));
        """, (self.username, topic_id, self[topic_id].as_json())

        self.logger.log(sql_query, sql_args)
        self.execute_simple(sql_query, sql_args)
        # also save a text version
        
        with (self.output_dir / f"nuggets_{topic_id}_{self.username}.json").open("w") as fw:
            fw.write(self[topic_id].as_json(indent=4))


def _flatten_dict(obj: Mapping[str, Mapping]):
    for key, val in obj.items():
        if isinstance(val, dict):
            yield from ( ((key, *cum_key), v) for cum_key, v in _flatten_dict(val) )
        else: 
            yield (key, ), val

def _multi_level_dict_to_series(obj: Mapping[str, Mapping], names= List[str]):
    return pd.Series(dict(_flatten_dict(obj))).rename_axis(names)


class SentenceAnnotationManager(SqliteManager):

    def __init__(
            self, db_path: str, 
            output_dir: str, log_manager: ActivityLogMananger,
            table_name: str, 
            content_obj: Dict,
            level_names: Tuple[str], slot_names: Union[Tuple[str], str]
        ):
            super().__init__(db_path, persistent_connection=False)
            self.logger = log_manager
            self.username = log_manager.username
            self.output_dir = Path(output_dir)
            self.table_name = table_name

            slot_names = (slot_names, ) if isinstance(slot_names, str) else slot_names
            
            content_df = _multi_level_dict_to_series(content_obj, level_names)
            self.content_df = content_df.rename('content').to_frame().assign(**{
                name: [None]*content_df.shape[0] for name in slot_names
            }).sort_index()

            if not self.table_exists(self.table_name):
                col_string = ", ".join(
                    f"{col} string" for col in self.content_df.index.names
                )
                self.execute_simple(f"""
                    create table if not exists {table_name} (
                        username string, {col_string},
                        slot_name string, annotation string,
                        ts datetime default current_timestamp
                    );
                """)

            record = pd.read_sql_query(
                f"select * from {self.table_name} where username = ?", self.conn, params=(self.username, )
            ).astype(str).sort_values('ts', ascending=False)\
            .groupby(self.content_df.index.names + ['slot_name']).first()\
            ['annotation'].unstack('slot_name')
        
            for slot in self.slot_names:
                if slot in record.columns:
                    self.content_df.loc[record.index, slot] = record[slot]

    
    @property
    def slot_names(self):
        return [ s for s in self.content_df.columns if s != 'content' ]

    @property
    def level_names(self):
        return self.content_df.index.names

    def __contains__(self, keys):
        return keys in self.content_df.index

    def __getitem__(self, keys):
        if keys not in self:
            return iter([])
        
        sel: Union[pd.DataFrame, pd.Series] = self.content_df.loc[keys]
        if isinstance(sel, pd.DataFrame):
            return sel.iterrows()
        return {
            key: NuggetSelection.from_json(val) if key == 'nugget' else val
            for key, val in sel.to_dict().items()
        }

    def is_all_done(self, *keys):
        if keys not in self:
            return True

        return not self.content_df.drop('content', axis=1).loc[keys].isna().any().any().item()

    def count_done(self, *keys, level=None):
        if keys not in self:
            return 0

        d = self.content_df.loc[keys].drop('content', axis=1)
        if level is None:
            return (~d.isna()).sum().sum().item()
    
        return d.groupby(level).apply(lambda x: ~x.isna().any().any()).sum().item()

    def count_job(self, *keys, level=None):
        if keys not in self:
            return 0

        if level is None: 
            return self.content_df.loc[keys].drop('content').size
        
        return self.content_df.loc[keys].index.get_level_values(level).unique().size

    def annotate(self, key: List[str], slot: str, annotation):
        assert slot in self.slot_names

        if isinstance(annotation, NuggetSelection):
            annotation = annotation.as_json()

        # prevent update if the value is the same
        if key in self and self.content_df.loc[pd.MultiIndex.from_tuples([key]), slot].iloc[0] == annotation:
            # print(f"-- same value for {key}, skip update")
            return

        self.content_df.loc[pd.MultiIndex.from_tuples([key]), slot] = annotation

        # save to db
        sql_query = f"""
            insert into {self.table_name} ({', '.join(self.level_names)}, slot_name, annotation, username) values
            ({', '.join(['?']*len(self.level_names))}, ?, ?, ?);
        """
        sql_args = (*key, slot, annotation, self.username)

        self.logger.log(sql_query, sql_args)
        self.execute_simple(sql_query, sql_args)


def session_set_default(session_key, default=None):
    if session_key not in st.session_state:
        st.session_state[session_key] = default if not callable(default) else default()
    
    return st.session_state[session_key]

# TODO: might want to control what page need to initilize what
def initialize_managers(task_config: TaskConfig, username: str):
    output_dir = Path(task_config.output_dir)

    logger = session_set_default(f'{task_config.name}/logger', lambda : ActivityLogMananger(output_dir / "log.db", username))
    session_set_default(
        f'{task_config.name}/nugget_manager', 
        lambda : NuggetSaverManager(output_dir / "annotation.db", output_dir, logger)
    )
    session_set_default(
        f'{task_config.name}/citation_assessment_manager', 
        lambda : SentenceAnnotationManager(
            output_dir / "annotation.db", # could be different
            output_dir, logger,
            table_name="sent2doc", 
            content_obj=task_config.cited_sentences, 
            slot_names='annot',
            level_names=['topic_id', 'doc_id', 'run_id', 'sent_id']
        )
    )
    session_set_default(
        f'{task_config.name}/report_annotation_manager', 
        lambda : SentenceAnnotationManager(
            output_dir / "annotation.db", # could be different
            output_dir, logger,
            table_name="sent2nugget", 
            content_obj=task_config.report_runs, 
            slot_names=('sent_indep', 'nugget'),
            level_names=['topic_id', 'run_id', 'sent_id']
        )
    )

def get_manager(task_config: TaskConfig, manager_name: str):
    return st.session_state[f"{task_config.name}/{manager_name}"]

def get_nugget_viewer(
        task_config: TaskConfig, username: str=None,
        from_all_users: bool=None, use_revised_nugget: bool=None
    ):
    if use_revised_nugget is None:
        use_revised_nugget = task_config.use_revised_nugget_only
    if from_all_users is None:
        from_all_users = task_config.combine_nuggets_from_multiple_users
    
    output_dir = Path(task_config.output_dir)
    return NuggetViewer(
        username=username, db_path=output_dir / "annotation.db",
        load_dir=output_dir,
        use_json=(task_config.load_nugget_from == 'json'),
        combine_nuggets_from_multiple_users=from_all_users,
        use_revised_nugget_only=use_revised_nugget
    )