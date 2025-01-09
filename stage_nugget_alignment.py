import streamlit as st
import pandas as pd
from pathlib import Path
import json

from page_utils import stpage, draw_bread_crumb, get_auth_manager, AuthManager

from task_resources import TaskConfig
from data_manager import NuggetSelection, SentenceAnnotationManager, session_set_default, get_manager, get_nugget_loader



@stpage(name="nugget_alignment", require_login=True)
@st.fragment
def nugget_alignment_page(auth_manager: AuthManager):
    if 'topic' not in st.query_params:
        st.query_params.clear()

    current_topic = st.query_params['topic']
    task_config: TaskConfig = st.session_state['task_configs'][st.query_params['task']]
    # initialize_managers(task_config, auth_manager.current_user)

    nugget_alignment_manager: SentenceAnnotationManager = get_manager(task_config, auth_manager.current_user, 'nugget_alignment_manager')
    sorted_report_list = sorted(task_config.report_runs[current_topic].keys())
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

    nugget_col, annotation_col = st.columns([5, 5])

    all_sent_ids = sorted([ sent_id for sent_id, _  in nugget_alignment_manager[current_topic, run_id]])
    

    def _on_sent_select(sent_id):
        st.session_state[f'active_sent/{current_topic}/{run_id}'] = sent_id


    # current_content_iter = nugget_alignment_manager[current_topic, run_id]
    with annotation_col.container(height=600, key="sentence_selection"):
        if nugget_alignment_manager.is_all_done(current_topic, run_id):
            st.html('<div class="is_done_flag"></div>')

        
        st.write("**Annotate for the active sentence in red box in the left panel**")

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
                type="primary" if should_highlight else "secondary"
            )

            # st.write(content)


    def _on_option_select(slot):
        sent_id = st.session_state[f'active_sent/{current_topic}/{run_id}']

        nugget_alignment_manager.annotate(
            key=(current_topic, run_id, sent_id), slot=slot, annotation=st.session_state[slot]
        )

    def _on_nugget_select():
        sent_id = st.session_state[f'active_sent/{current_topic}/{run_id}']
        if st.session_state['nugget_question'] in task_config.additional_nugget_options:
            st.session_state["nugget_answer"] = st.session_state['nugget_question']
        
        if "nugget_answer" not in st.session_state or st.session_state['nugget_answer'] is None:
            return
        
        if task_config.sentence_allow_multiple_nuggets:
            current_nugget: NuggetSelection = nugget_alignment_manager[current_topic, run_id, sent_id]['nugget']
        else:
            current_nugget = NuggetSelection()
        
        current_nugget.add((st.session_state['nugget_question'], st.session_state['nugget_answer']))
        nugget_alignment_manager.annotate(key=(current_topic, run_id, sent_id), slot="nugget", annotation=current_nugget)

        st.session_state['nugget_question'] = None
        st.session_state['nugget_answer'] = None

    def _on_nugget_unselect():
        sent_id = st.session_state[f'active_sent/{current_topic}/{run_id}']

        assert len(st.session_state['nugget_unselect']['edited_rows']) == 1
        removing_row_idx, _action = next(iter(st.session_state['nugget_unselect']['edited_rows'].items()))
        assert _action['delete']

        current_nugget: NuggetSelection = nugget_alignment_manager[current_topic, run_id, sent_id]['nugget']

        removing_row = current_nugget.as_dataframe().iloc[removing_row_idx]
        current_nugget.remove((removing_row['Question'], removing_row['Answer']))

        nugget_alignment_manager.annotate(key=(current_topic, run_id, sent_id), slot="nugget", annotation=current_nugget)


    with nugget_col.container(height=600):
        # key = _make_key(current_topic, run_id, sent_id)

        # st.write("**Annotate for the active sentence**")
        active_sent_id = st.session_state[f'active_sent/{current_topic}/{run_id}']

        # # HACK hardcoding sent_indep here is not cool...
        # pre_select = nugget_alignment_manager[current_topic, run_id, active_sent_id]['sent_indep']
        # if pd.isna(pre_select):
        #     pre_select = None

        # st.segmented_control(
        #     label="Select applicable option for the active sentence",
        #     key='sent_indep',
        #     selection_mode="single", 
        #     options=task_config.sentence_independent_option,
        #     format_func=str.title,
        #     default=pre_select,
        #     args=('sent_indep', ),
        #     on_change=_on_option_select
        # )

        st.write("")
        st.write("**Nugget Selection For The Active Sentence**")
        
        nuggets_for_selection = nugget_loader[current_topic].as_nugget_dict(only_answers=True)
        question_select = st.selectbox(
            label="Select nugget question",
            key="nugget_question",
            options=sorted(nuggets_for_selection.keys()) + task_config.additional_nugget_options,
            format_func=lambda x: f"**{x}**" if x in task_config.additional_nugget_options else x,
            index=None,
            placeholder="...",
            on_change=_on_nugget_select
        )

        if question_select is not None:

            st.selectbox(
                label="Select nugget answer",
                key="nugget_answer",
                options=sorted(nuggets_for_selection[question_select]) + ["**Other acceptable answer**"],
                index=None,
                placeholder="...",
                on_change=_on_nugget_select
            )

        st.write("**Selected Nuggets**")

        st.data_editor(
            nugget_alignment_manager[current_topic, run_id, active_sent_id]['nugget'].as_dataframe().assign(delete=False),
            column_order=["delete", "Question", "Answer"],
            disabled=("Question", "Answer"),
            use_container_width=True,
            hide_index=True,
            column_config={
                "delete": st.column_config.CheckboxColumn("Delete?", width=None, default=False)
            },
            key="nugget_unselect",
            on_change=_on_nugget_unselect
        )