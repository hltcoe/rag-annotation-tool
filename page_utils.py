from typing import Callable, List
import streamlit as st
import sqlite3

import uuid
import random
import string
from hashlib import md5

from data_manager import SqliteManager, session_set_default

_page_mapper = {}

def random_key():
    return str(uuid.uuid4())

def draw_pages(db_path, get_param='page', default_page=None):
    
    auth_manager = get_auth_manager(db_path)

    if get_param not in st.query_params:
        st.query_params[get_param] = default_page
    
    if st.query_params[get_param] in _page_mapper:
        func, require_login, require_admin = _page_mapper[st.query_params[get_param]]
        if require_login and auth_manager.current_user is None:
            if 'login' not in _page_mapper:
                st.exception(RuntimeError(f"Login page not implemented"))
            else:
                _page_mapper['login'][0](auth_manager)
        elif require_admin and not auth_manager.is_admin:
            st.write("""# Well... you are not suppose to be here... """)
        else:
            func(auth_manager)

    else:
        st.write("""
            # This is suppose to be 404
            If you know what that means...
        """)


def stpage(name: str, require_login=False, require_admin=False):
    # assert name not in _page_mapper

    def dec(func: Callable):
        _page_mapper[name] = (func, require_login, require_admin)
        return func

    return dec

def goto_page(page_name, collapse_sidebar: bool=False, **kwargs):
    if collapse_sidebar:
        st.session_state['sidebar_state'] = "collapsed" 
    st.query_params.page = page_name

    for key, val in kwargs.items():
        st.query_params[key] = val


def draw_bread_crumb(
        crumbs: List[str], n_jobs: int, n_done: int, 
        key: str, icon=":material/double_arrow:"
    ):
    session_set_default(key, 0)

    def _change_doc():
        if st.session_state.doc_nav == 'back':
            st.session_state[key] -= 1
        elif st.session_state.doc_nav == 'next':
            st.session_state[key] += 1
        
        st.session_state[key] = max(st.session_state[key], 0)
        st.session_state[key] = min(st.session_state[key], n_jobs-1)

        st.session_state.doc_nav = None
        

    crumb_col, nav_col = st.columns([7, 1], vertical_alignment='center')

    # TODO: make things clickable and add modal for selecting doc and topic
    crumb_col.write(f" {icon} ".join(
        piece.format(current_idx=st.session_state[key]+1, n_done=n_done, n_jobs=n_jobs)
        for piece in crumbs
    ))

    nav_col.segmented_control(
        "doc_nav",
        options=['back', 'next'],
        format_func={'back': ":material/arrow_back: Back", 'next': ":material/arrow_forward: Next"}.__getitem__,
        selection_mode="single",
        label_visibility='collapsed', 
        key='doc_nav',
        on_change=_change_doc
    )

    return st.session_state[key]


def _get_session_id():
    if 'ajs_anonymous_id' not in st.context.cookies:
        return None
    return st.context.cookies['ajs_anonymous_id']


def _generate_salt(length: int=16):
    return ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(length))


class AuthManager(SqliteManager):

    def __init__(self, db_path):
        super().__init__(db_path, persistent_connection=False)
        self.session_user_mapping = {}

        self.init_db()

    @property
    def current_user(self):
        if _get_session_id() is None:
            st.error("Please refresh the browser tab.")

        if _get_session_id() not in self.session_user_mapping:
            return None
        
        return self.session_user_mapping[_get_session_id()][0]

    @property
    def is_admin(self):
        if _get_session_id() not in self.session_user_mapping:
            return False
        return self.session_user_mapping[_get_session_id()][1]
    
    def init_db(self):
        if not self.table_exists("users"):
            self.execute_simple("""create table if not exists users (username string, salt string, password string, admin int default 0);""")
            self.add_user("root", "nisthltcoeeugene", admin=True, table_init=True) # add the default one

    def add_user(self, username: str, password: str, admin=False, table_init=False):
        if not table_init:
            assert self.is_admin

        count: int = self.execute_simple("""select count(rowid) from users where username==?""", (username, ))[0][0]
        if count > 0:
            raise ValueError(f"Username {username} already exists.")

        salt = _generate_salt()
        password = md5((password + salt).encode()).hexdigest()
        self.execute_simple("""insert into users (username, salt, password, admin) values (?, ?, ?, ?)""", (username, salt, password, int(admin)))

        return self.execute_simple("select rowid from users where username==?", (username, ))[0]

    def delete_user(self, username: str):
        assert self.is_admin
        self.execute_simple("""delete from users where username=?;""", (username, ))


    def _validate(self, username, password):
        ret = self.execute_simple("""select salt, password, admin from users where username==?;""", (username, ))
        if len(ret) == 0:
            st.error(f"Wrong username or password.", icon="🚨")
            return False, False

        salt, salted_password, admin = ret[0]
        if md5((password + salt).encode()).hexdigest() != salted_password:
            st.error(f"Wrong username or password.", icon="🚨")
            return False, False

        return True, admin != 0

    def login(self, username, password):
        is_success, is_admin = self._validate(username, password)
        
        if is_success:
            assert _get_session_id() is not None
            self.session_user_mapping[ _get_session_id() ] = (username, is_admin)
        
        return is_success

    def change_password(self, old_password, new_password):
        is_success, _ = self._validate(self.current_user, old_password)
        
        if is_success:
            salt = _generate_salt()
            new_password = md5((new_password + salt).encode()).hexdigest()
            self.execute_simple("""UPDATE users SET salt=?, password=? where username=?;""", (salt, new_password, self.current_user))
        
        return is_success

    def get_all_users(self):
        assert self.is_admin

        return sorted([
            (username, is_admin != 0)
            for username, is_admin in self.execute_simple("""select username, admin from users;""")
        ], key=lambda x: ~x[1])


    def logout(self):
        sid = _get_session_id()
        if sid in self.session_user_mapping:
            del self.session_user_mapping[ _get_session_id() ]



@st.cache_resource
def get_auth_manager(db_path):
    return AuthManager(db_path)






