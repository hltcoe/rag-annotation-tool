from typing import Callable, Dict
import streamlit as st
import pandas as pd
from pathlib import Path

from page_utils import stpage, draw_bread_crumb, get_auth_manager, random_key, AuthManager

from task_resources import TaskConfig
from data_manager import NuggetSaverManager, NuggetSet, SentenceAnnotationManager, initialize_managers, session_set_default, get_manager
import ir_datasets as irds


@st.cache_data(ttl=600)
def _get_doc_content(service, collection_id, doc_id):
    if service == 'ir_datasets':
        doc = irds.load(collection_id).docs.lookup(doc_id)
        return {
            'title': doc.title if hasattr(doc, 'title') else "",
            'text': doc.default_text()
        }
    # TODO implement other stuff
    return {'title': "", "text": f"Suppose to be {service} {collection_id} // {doc_id}"}


def draw_nugget_editor(
        nugget_set: NuggetSet, current_doc_id: str, key_prefix: str,
        on_add_nugget: Callable=None, on_delete_nugget: Callable=None
    ):

    def _add_answer(nidx, selection_key, add_key = None):
        # print(nugget_set[nidx][0], st.session_state[add_key])

        question = nugget_set[nidx][0]
        if add_key is not None:
            answers = [st.session_state[add_key]]
        elif '+' not in st.session_state[selection_key]:
            answers = st.session_state[selection_key]
        else:
            # click on + but not yet add the answer
            return 
        
        # check if it is delete or add
        original_answers = nugget_set.get(question)
        if original_answers is not None and add_key is None: # make sure we are not adding new answer
            original_selected = { answer for answer, doc_set in original_answers.items() if current_doc_id in doc_set }
            deleted = (original_selected - set(answers))
            if len(deleted) > 0:
                print(set(answers) - original_selected)
                assert len(set(answers) - original_selected) == 0, "You can't do delete and add at the same time..."

                if on_delete_nugget:
                    on_delete_nugget(current_doc_id, question, deleted)
                    return
                
        # Adding
        success = None
        if on_add_nugget:
            success = on_add_nugget(current_doc_id, question, answers)
            
        if success is None or success:
            del st.session_state[selection_key]
            if add_key is not None:
                del st.session_state[add_key]
    
    for nidx, (question, a_dict) in enumerate(nugget_set.iter_nuggets()):
        q_col, a_col, input_col = st.columns([1,1,1], vertical_alignment='center')
        
        
        q_col.write(question)
        
        answer_selection = a_col.pills(
            label="answers", 
            options=sorted(a_dict.keys()) + ["+"],
            format_func=lambda k: ":material/add:" if k == "+" else f"{k} ({len(a_dict[k])})",
            default=[ a for a, dids in a_dict.items() if current_doc_id in dids ],
            selection_mode='multi',
            label_visibility='collapsed',
            key=f"{key_prefix}/nugget/{nidx}/select",
            args=(nidx, f"{key_prefix}/nugget/{nidx}/select"),
            on_change=_add_answer
        )

        if "+" in answer_selection:
            input_col.text_input(
                label="add_answer",
                placeholder="New answer...",
                key=f"{key_prefix}/nugget/{nidx}/add",
                label_visibility='collapsed',
                args=(nidx, f"{key_prefix}/nugget/{nidx}/select", f"{key_prefix}/nugget/{nidx}/add"),
                on_change=_add_answer
            )

    def _new_nugget():
        question = st.session_state[f"{key_prefix}/nugget/new/question"]
        answer = st.session_state[f"{key_prefix}/nugget/new/answer"]
        if question is None or question == "" or answer is None or answer == "":
            return
        
        success = None
        if on_add_nugget:
            success = on_add_nugget(current_doc_id, question, [answer])
        if success is None or success == True:
            st.session_state[f"{key_prefix}/nugget/new/question"] = ""
            st.session_state[f"{key_prefix}/nugget/new/answer"] = ""

            
    # add new nugget
    q_add_col, a_add_col = st.columns([1,2], vertical_alignment='center')
    q_add_col.text_input(
        label="add_question",
        placeholder="New question...",
        key=f"{key_prefix}/nugget/new/question",
        label_visibility="collapsed",
        on_change=_new_nugget
    )
    a_add_col.text_input(
        label="add_answer",
        placeholder="New answer...",
        key=f"{key_prefix}/nugget/new/answer",
        label_visibility="collapsed",
        on_change=_new_nugget
    )

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
    initialize_managers(task_config, auth_manager.current_user)
    
    sorted_doc_list = sorted(task_config.cited_sentences[current_topic].keys())

    citation_assessment_manager: SentenceAnnotationManager = get_manager(task_config, 'citation_assessment_manager')
    nugget_manager: NuggetSaverManager = get_manager(task_config, 'nugget_manager')
    nugget_set = nugget_manager[current_topic]
    
    current_doc_offset = draw_bread_crumb(
        crumbs=[
            st.query_params.task, "Citation Assessment", 
            f"Topic {st.query_params.topic}",
            "Doc #{current_idx} ({n_done}/{n_jobs} Documents Done)"
        ],
        n_jobs=len(sorted_doc_list), 
        n_done=citation_assessment_manager.count_done(current_topic, level='doc_id'),
        key=f'{task_config.name}/citation/{current_topic}/current_doc_offset',
    )
    
    doc_id = sorted_doc_list[current_doc_offset]

    doc_col, annotation_col = st.columns([4, 6])

    
    with doc_col.container(height=450):
        doc_content = _get_doc_content(task_config.doc_service, task_config.collection_id, doc_id)
        if doc_content['title'] != "":
            st.write(f"**{doc_content['title']}**")
        st.caption(f"Doc ID: {doc_id}")
        st.write(doc_content['text'])
    
    with doc_col.container(height=250):
        st.write(f"**Topic {current_topic}**")
        for key, val in task_config.requests[current_topic].items():
            st.write(f"**{key.replace('_', ' ').title()}**: {val}")
            
    def _on_add_nugget(doc_id, question, answers):
        nugget_set.add(question, [ (doc_id, answer) for answer in answers ])
        nugget_manager.flush(current_topic)

    def _on_delete_nugget(doc_id, question, deleting_answers):
        nugget_set.remove(question, doc_id, deleting_answers)
        nugget_manager.flush(current_topic)


    with annotation_col.container(height=350):
        st.write("**Nugget editor**")

        draw_nugget_editor(
            nugget_set, 
            current_doc_id=doc_id,
            key_prefix=f'{task_config.name}/citation/{current_topic}/',
            on_add_nugget=_on_add_nugget,
            on_delete_nugget=_on_delete_nugget
        )

    
    current_content_iter = citation_assessment_manager[current_topic, doc_id]

    _make_key = lambda current_topic, doc_id, run_id, sent_id: f"supportive {current_topic} {doc_id} {run_id} {sent_id}"
    def _sent_on_select(*key):
        # print(auth_manager.current_user, *key, st.session_state[_make_key(*key)])

        citation_assessment_manager.annotate(
            key=key, slot='annot', annotation=st.session_state[_make_key(*key)]
        )
        

    with annotation_col.container(height=350):
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


