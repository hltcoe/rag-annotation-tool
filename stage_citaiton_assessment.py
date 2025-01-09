from typing import Callable, Dict
import streamlit as st
import pandas as pd
from pathlib import Path

from page_utils import stpage, draw_bread_crumb, toggle_button, get_auth_manager, random_key, AuthManager

from task_resources import TaskConfig
from data_manager import NuggetSaverManager, AnnotationManager, get_manager, get_doc_content
from nugget_editor import draw_nugget_editor


@st.dialog("Full Report", width="large")
def show_full_report(run_dict: Dict[str, str], highlight_sent_id: str):
    for sent_id, text in sorted(run_dict.items(), key=lambda x: int(x[0])):
        if highlight_sent_id == sent_id:
            text = f":orange-background[{text}]"
        st.markdown(text)
        


@stpage(name='citation_assessment', require_login=True)
@st.fragment
def citation_assessment_page(auth_manager: AuthManager):
    if 'topic' not in st.query_params:
        st.query_params.clear()

    current_topic = st.query_params['topic']
    task_config: TaskConfig = st.session_state['task_configs'][st.query_params['task']]
    # initialize_managers(task_config, auth_manager.current_user)
    
    sorted_doc_list = sorted(task_config.cited_sentences[current_topic].keys())

    citation_assessment_manager: AnnotationManager = get_manager(task_config, auth_manager.current_user, 'citation_assessment_manager')
    nugget_manager: NuggetSaverManager = get_manager(task_config, auth_manager.current_user, 'nugget_manager')
    nugget_set = nugget_manager[current_topic]
    
    current_doc_offset = draw_bread_crumb(
        crumbs=[
            st.query_params.task, "Citation Assessment and Support", 
            f"Topic {st.query_params.topic}",
            "Doc #{current_idx} ({n_done}/{n_jobs} Documents Done)"
        ],
        n_jobs=len(sorted_doc_list), 
        n_done=citation_assessment_manager.count_done(current_topic, level='doc_id'),
        key=f'{task_config.name}/citation/{current_topic}/current_doc_offset',
        check_done=lambda idx: citation_assessment_manager.is_all_done(current_topic, sorted_doc_list[idx])
    )


    if citation_assessment_manager.is_all_done(current_topic):
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
        
    current_content_iter = citation_assessment_manager[current_topic, doc_id]

    _make_key = lambda current_topic, doc_id, run_id, sent_id: f"supportive {current_topic} {doc_id} {run_id} {sent_id}"
    def _sent_on_select(*key):
        # print(auth_manager.current_user, *key, st.session_state[_make_key(*key)])

        citation_assessment_manager.annotate(
            key=key, slot='annot', annotation=st.session_state[_make_key(*key)]
        )
        

    with annotation_col.container(height=400):
        if citation_assessment_manager.is_all_done(current_topic, doc_id):
            st.html('<div class="is_done_flag"></div>')

        
        st.write("**Sentence assessment**")

        st.html('<div class="fake_button_container">')


        for (run_id, sent_id), content in current_content_iter:
            key = _make_key(current_topic, doc_id, run_id, sent_id)

            sent_col, option_col = st.columns([4, 1], vertical_alignment="center")

            # if key in st.session_state and st.session_state[key] is not None:
            text = f":gray[{content['content']}]" if content['annot'] is not None else content['content']

            if sent_col.button(text, key=f"{key}/sent_content"):
                show_full_report(task_config.report_runs[current_topic][run_id], sent_id)


            option_col.selectbox(
                label=key, 
                options=task_config.sentence_to_document_options,
                format_func=str.title,
                index=None if content['annot'] is None else task_config.sentence_to_document_options.index(content['annot']),
                placeholder="...",
                label_visibility='collapsed',
                key=key,
                args=(current_topic, doc_id, run_id, sent_id),
                on_change=_sent_on_select
            )

    def _on_select_nugget_answer(doc_id, question, answers):
        nugget_set.add(question, [ (doc_id, answer) for answer in answers ])
        nugget_manager.flush(current_topic)

    def _on_unselect_nugget_answer(doc_id, question, deleting_answers):
        nugget_set.remove(question, doc_id, deleting_answers)
        nugget_manager.flush(current_topic)
    
    def _on_assign_group(question, group_name):
        nugget_set.set_group(question, group_name)
        nugget_manager.flush(current_topic)

    def _on_rename_group(old_group_name, new_group_name):
        nugget_set.rename_group(old_group_name, new_group_name)
        nugget_manager.flush(current_topic)

    with annotation_col.container(height=205, border=None):
        draw_nugget_editor(
            nugget_set, 
            current_doc_id=doc_id,
            title="Nugget Editor and Grouper",
            key_prefix=f'{task_config.name}/citation/{current_topic}/',
            on_select_nugget_answer=_on_select_nugget_answer,
            on_unselect_nugget_answer=_on_unselect_nugget_answer,
            on_assign_group=_on_assign_group,
            on_rename_group=_on_rename_group,
            allow_nugget_question_creation=False
        )
