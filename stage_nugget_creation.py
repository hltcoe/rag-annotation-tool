from typing import Callable, Dict
import streamlit as st
import pandas as pd
from pathlib import Path

from page_utils import stpage, draw_bread_crumb, toggle_button, get_auth_manager, random_key, AuthManager

from task_resources import TaskConfig
from data_manager import NuggetSaverManager, NuggetSet, SentenceAnnotationManager, \
                         get_manager, get_doc_content
from nugget_editor import draw_nugget_editor


@stpage(name='nugget_creation', require_login=True)
@st.fragment()
def nugget_creation_page(auth_manager: AuthManager):
    if 'topic' not in st.query_params:
        st.query_params.clear()

    current_topic = st.query_params['topic']
    task_config: TaskConfig = st.session_state['task_configs'][st.query_params['task']]
    # initialize_managers(task_config, auth_manager.current_user)
    
    # TODO: or random instead of sorted
    sorted_doc_list = sorted(task_config.pooled_docs[current_topic])

    # binary document relevance is inferred here -- mostly for progress tracking
    # real graded relevance should be inferred by the nugget importance
    relevance_assessment_manager: SentenceAnnotationManager = get_manager(task_config, auth_manager.current_user, 'relevance_assessment_manager')
    nugget_manager: NuggetSaverManager = get_manager(task_config, auth_manager.current_user, 'nugget_manager')
    nugget_set = nugget_manager[current_topic]
    
    current_doc_offset = draw_bread_crumb(
        crumbs=[
            st.query_params.task, "Nugget Creation", 
            f"Topic {st.query_params.topic}",
            "Doc #{current_idx} ({n_done}/{n_jobs} Documents Done)"
        ],
        n_jobs=len(sorted_doc_list), 
        n_done=relevance_assessment_manager.count_done(current_topic, level='doc_id'),
        key=f'{task_config.name}/nugget_creation/{current_topic}/current_doc_offset',
        check_done=lambda idx: relevance_assessment_manager.is_all_done(current_topic, sorted_doc_list[idx])
    )


    if relevance_assessment_manager.is_all_done(current_topic):
        st.toast(f'Topic {current_topic} is done.', icon=':material/thumb_up:')
    
    doc_id = sorted_doc_list[current_doc_offset]

    with st.container(height=100):
        st.write(f"**Topic {current_topic}**")
        for key, val in task_config.requests[current_topic].items():
            st.write(f"**{key.replace('_', ' ').title()}**: {val}")
            
    doc_col, annotation_col = st.columns([4, 6])

    with doc_col.container(height=620):
        doc_content = get_doc_content(task_config.doc_service, task_config.collection_id, doc_id)
        if doc_content['title'] != "":
            st.write(f"**{doc_content['title']}**")
        st.caption(f"Doc ID: {doc_id}")
        st.write(doc_content['text'])
    
    def _on_select_nugget_answer(doc_id, question, answers):
        nugget_set.add(question, [ (doc_id, answer) for answer in answers ])
        nugget_manager.flush(current_topic)
        _on_check_no_citation_box(doc_id, "0")

    def _on_unselect_nugget_answer(doc_id, question, deleting_answers):
        nugget_set.remove(question, doc_id, deleting_answers)
        nugget_manager.flush(current_topic)
    
    def _on_assign_group(question, group_name):
        nugget_set.set_group(question, group_name)
        nugget_manager.flush(current_topic)

    def _on_rename_group(old_group_name, new_group_name):
        nugget_set.rename_group(old_group_name, new_group_name)
        nugget_manager.flush(current_topic)

    def _on_check_no_citation_box(doc_id, check=None):
        if check is None:
            check = st.session_state[f'{task_config.name}/nugget_creation/{current_topic}/{doc_id}/no_nugget']
            check = "1" if check else "0"

        relevance_assessment_manager.annotate(
            key=(current_topic, doc_id),
            slot='no_nugget_found', 
            annotation=check
        )

    with annotation_col.container(height=620):

        pre_select = relevance_assessment_manager[current_topic, doc_id]['no_nugget_found']
        if pd.isna(pre_select):
            pre_select = "0"


        st.checkbox(
            "No relevant nugget in this document.",
            key=f'{task_config.name}/nugget_creation/{current_topic}/{doc_id}/no_nugget',
            args=(doc_id, ),
            value=pre_select == "1",
            disabled=nugget_manager[current_topic].doc_has_nugget(doc_id),
            on_change=_on_check_no_citation_box
        )

        draw_nugget_editor(
            nugget_set, 
            current_doc_id=doc_id,
            title="Nugget Editor and Grouper",
            key_prefix=f'{task_config.name}/nugget_creation/{current_topic}/',
            on_select_nugget_answer=_on_select_nugget_answer,
            on_unselect_nugget_answer=_on_unselect_nugget_answer,
            on_assign_group=_on_assign_group,
            on_rename_group=_on_rename_group
        )



