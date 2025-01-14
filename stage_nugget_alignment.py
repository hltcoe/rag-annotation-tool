import streamlit as st
import pandas as pd
from pathlib import Path
import json

from page_utils import stpage, draw_bread_crumb, stable_hash, get_auth_manager, AuthManager

from task_resources import TaskConfig
from data_manager import NuggetSelection, AnnotationManager, session_set_default, get_manager, get_nugget_loader
from nugget_editor import draw_nugget_editor


@stpage(name="nugget_alignment", require_login=True)
@st.fragment
def nugget_alignment_page(auth_manager: AuthManager):
    if 'topic' not in st.query_params:
        st.query_params.clear()

    current_topic = st.query_params['topic']
    task_config: TaskConfig = st.session_state['task_configs'][st.query_params['task']]
    # initialize_managers(task_config, auth_manager.current_user)

    nugget_alignment_manager: AnnotationManager = get_manager(task_config, auth_manager.current_user, 'nugget_alignment_manager')
    # TODO: hash sort based on username
    sorted_report_list = sorted(task_config.report_runs[current_topic].keys(), key=lambda x: stable_hash(f"{auth_manager.current_user} {x}"))
    nugget_loader = get_nugget_loader(task_config, auth_manager.current_user)

    run_id_offset = draw_bread_crumb(
        crumbs=[
            st.query_params.task, "Citation Assessment", 
            f"Topic {st.query_params.topic}",
            "Report #{current_idx} ({n_done}/{n_jobs} Reports Done)"
        ],
        n_jobs=len(sorted_report_list), 
        n_done=nugget_alignment_manager.count_done(current_topic, level='run_id'),
        key=f'{task_config.name}/report/{current_topic}/current_report_offset',
        check_done=lambda idx: nugget_alignment_manager.is_all_done(current_topic, sorted_report_list[idx])
    )

    run_id = sorted_report_list[run_id_offset]

    with st.container(height=100):
        st.write(f"**Topic {current_topic}**")
        for key, val in task_config.requests[current_topic].items():
            st.write(f"**{key.replace('_', ' ').title()}**: {val}")

    annotation_col, nugget_col = st.columns([5, 5])    

    def _on_sent_select(sent_id):
        st.session_state[f'active_sent/{current_topic}/{run_id}'] = sent_id


    with annotation_col.container(height=600, key="sentence_selection"):
        if nugget_alignment_manager.is_all_done(current_topic, run_id):
            st.html('<div class="is_done_flag"></div>')

        
        st.write("**Select applicable nuggets for the active sentence in marked in red at the right panel**")

        sent_iter = lambda : sorted(nugget_alignment_manager[current_topic, run_id], key=lambda x: int(x[0]))
        
        if f'active_sent/{current_topic}/{run_id}' not in st.session_state:
            # find first not done
            for sent_id, content in sent_iter():
                if not nugget_alignment_manager.is_all_done(current_topic, run_id, sent_id):
                    st.session_state[f'active_sent/{current_topic}/{run_id}'] = sent_id
                    break
            else:
                st.session_state[f'active_sent/{current_topic}/{run_id}'] = "0"

            
        for sent_id, content in sent_iter():
            
            text_content = content['content']
            # not_done = content['sent_indep'] is None or content['nugget'] is None
            not_done = not nugget_alignment_manager.is_all_done(current_topic, run_id, sent_id)
            should_highlight = (st.session_state[f'active_sent/{current_topic}/{run_id}'] == sent_id)

            st.button(
                label=text_content,
                icon=':material/check_box_outline_blank:' if not_done else ':material/select_check_box:',
                use_container_width=True,
                args=(sent_id, ),
                on_click=_on_sent_select,
                type="primary" if should_highlight else "secondary",
                key=f"{current_topic}/{run_id}/{sent_id}/sent_select_btn"
            )

            # st.write(content)


    def _on_nugget_select(sent_id, question, answers):
        if task_config.sentence_allow_multiple_nuggets:
            current_nugget: NuggetSelection = nugget_alignment_manager[current_topic, run_id, sent_id]['nugget']
        else:
            current_nugget = NuggetSelection()
        
        for a in answers:
            current_nugget.add((question, a))
            
        nugget_alignment_manager.annotate(key=(current_topic, run_id, sent_id), slot="nugget", annotation=current_nugget)
        st.rerun()

    def _on_nugget_unselect(sent_id, question, answers_to_remove):
        current_nugget: NuggetSelection = nugget_alignment_manager[current_topic, run_id, sent_id]['nugget']

        for a in answers_to_remove:
            current_nugget.remove((question, a))

        nugget_alignment_manager.annotate(key=(current_topic, run_id, sent_id), slot="nugget", annotation=current_nugget)


    with nugget_col.container(height=600, border=False):
        
        active_sent_id = st.session_state[f'active_sent/{current_topic}/{run_id}'] 

        nuggets_for_selection = nugget_loader[current_topic].clone()
        for q in nuggets_for_selection.get_all_questions():
            nuggets_for_selection.add(q, [("_", "*Other acceptable answer*")])

        nuggets_for_selection.add("*Other Options*", [
            ("_", f"*{o}*")
            for o in task_config.additional_nugget_options
        ])

        # add selected nuggets
        for q, a in nugget_alignment_manager[current_topic, run_id, active_sent_id]['nugget']:
            nuggets_for_selection.add(q, [(active_sent_id, a)])

        draw_nugget_editor(
            nuggets_for_selection,
            # title="Nugget Selection For The Active Sentence",
            current_doc_id=active_sent_id,
            show_counts=False,
            key_prefix=f"{current_topic}/{run_id}/{active_sent_id}/nugget_selector",
            allow_nugget_answer_selection=True,
            allow_nugget_answer_creation=False,
            allow_nugget_question_creation=False,
            allow_nugget_group_edit=False,
            allow_nugget_question_edit=False,
            on_select_nugget_answer=_on_nugget_select,
            on_unselect_nugget_answer=_on_nugget_unselect
        )

