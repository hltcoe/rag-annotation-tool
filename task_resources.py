from typing import Iterable, Set, Tuple, List, Dict, Literal, Mapping, Union
from dataclasses import dataclass, asdict, field
from pathlib import Path

import streamlit as st

import json


@st.cache_data
def _load_json_resource(fn: str):
    with open(fn) as fr:
        data = json.load(fr)
    return data

@dataclass
class TaskConfig:
    name: str = None
    output_dir: str = None # need to save nuggets and annotation
    
    job_assignment: Dict[str, List[str]] = None # username -> [... topic_id]

    topic_file: str = None
    topic_id_field: str = "request_id"
    topic_fields: List[str] = field(default_factory=lambda :['problem_statement', 'background'])

    doc_pools_path: str = None # a json with {'topic_id: ['doc_id', ...] }

    # pooling decisions should live outside of this app
    cited_sentences_path: str = None # a json with {'topic_id': {'doc_id': {'run_id': {'sen_id': 'sentence_text', ...}, ...} ...}, ...}
    sentence_to_document_options: List[str] = field(default_factory=lambda :["not supported", "supported"])

    force_citation_asssessment_before_report: bool = True
    load_nugget_from: Literal['db', 'json'] = "json"
    combine_nuggets_from_multiple_users: bool = False
    use_revised_nugget_only: bool = True

    report_runs_path: str = None # a json with {'topic_id: {'run_id': {'sen_id': 'sentence_text'}}, ...}
    sentence_independent_option: List[str] = field(default_factory=lambda :["no need citations", "need citation"])
    sentence_allow_multiple_nuggets: bool = False
    additional_nugget_options: List[str] = field(default_factory=lambda :[
        "Other crucial nugget to the request",
        "Topical nugget",
        "Irrelevant nugget",
        "No nugget found"
    ])
    
    collection_id: str = None    
    doc_service: Literal['ir_datasets', 'http_api'] = 'ir_datasets'

    @classmethod
    def from_json(cls, file_path: str):
        return cls(**json.loads(Path(file_path).read_text()))
    
    def to_json(self, file_path: str):
        data = asdict(self)
        with open(file_path, "w") as fw:
            json.dump(data, fw, indent=4, allow_nan=True)   

    def __post_init__(self):
        self.requests: Dict[str, Dict[str, str]] = {
            topic[self.topic_id_field]: { key: topic[key] for key in self.topic_fields }
            for topic in map(json.loads, open(self.topic_file))
        }
        self.pooled_docs: Dict[str, List[str]] = _load_json_resource(self.doc_pools_path)
        self.cited_sentences: Dict[str, Dict[str, Dict[str, Dict[str, str]]]] = _load_json_resource(self.cited_sentences_path)
        self.report_runs: Dict[str, Dict[str, Dict[str, str]]] = _load_json_resource(self.report_runs_path)


