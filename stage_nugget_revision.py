from typing import Literal
import streamlit as st
import pandas as pd
from pathlib import Path

from page_utils import stpage, draw_bread_crumb, toggle_button, get_auth_manager, random_key, AuthManager

from task_resources import TaskConfig
from data_manager import NuggetSaverManager, NuggetSet, session_set_default, get_manager, get_nugget_loader
from nugget_editor import draw_nugget_editor


# @st.fragment
@stpage("nugget_revision", require_login=True, require_admin=True)
def nugget_revision_page(auth_manager: AuthManager):
    if 'topic' not in st.query_params:
        st.query_params.clear()
    
    current_topic = st.query_params['topic']
    task_config: TaskConfig = st.session_state['task_configs'][st.query_params['task']]
    # initialize_managers(task_config, auth_manager.current_user)

    key_prefix = f'{task_config.name}/nugget_revision/{current_topic}'

    nugget_manager: NuggetSaverManager = get_manager(task_config, auth_manager.current_user, 'nugget_manager')
    nugget_loader = get_nugget_loader(
        task_config, auth_manager.current_user, from_all_users=True, use_revised_nugget=False
    )

    session_set_default(f"{key_prefix}/redo_buffer", [])
    session_set_default(f"{key_prefix}/redo_pointer", -1)
    def _push_new_action(to_save):
        current_pointer = st.session_state[f"{key_prefix}/redo_pointer"]
        if current_pointer <= 0:
            st.session_state[f"{key_prefix}/redo_buffer"].append(to_save)
        else:
            old_buffer: list = st.session_state[f"{key_prefix}/redo_buffer"]
            st.session_state[f"{key_prefix}/redo_buffer"] = [ *old_buffer[:current_pointer], to_save ]
            st.session_state[f"{key_prefix}/redo_pointer"] = 0

    def _move_pointer(direction: Literal["undo", "redo", "to_head"]):
        if direction == "undo":
            if st.session_state[f"{key_prefix}/redo_pointer"] > -len(st.session_state[f"{key_prefix}/redo_buffer"]):
                st.session_state[f"{key_prefix}/redo_pointer"] -= 1
            else:
                st.toast('No more buffer to undo.', icon=':material/cancel:')
        elif direction == "redo":
            if st.session_state[f"{key_prefix}/redo_pointer"] < -1:
                st.session_state[f"{key_prefix}/redo_pointer"] += 1
            else:
                st.toast('No more buffer to redo.', icon=':material/cancel:')
        elif direction == "to_head":
            st.session_state[f"{key_prefix}/redo_pointer"] = -len(st.session_state[f"{key_prefix}/redo_buffer"])

        return st.session_state[f"{key_prefix}/redo_buffer"][ st.session_state[f"{key_prefix}/redo_pointer"] ]

    def _on_select_action():
        action = st.session_state[f"{key_prefix}/action_btn"]
        st.session_state[f"{key_prefix}/action_btn"] = None

        if f"{key_prefix}/edit_nuget_set" not in st.session_state:
            return 
        
        if action == "save":
            nugget_manager.save_revised_nugget(current_topic, st.session_state[f"{key_prefix}/edit_nuget_set"])
            st.toast('Nugget is saved', icon=':material/thumb_up:')
        elif action == "undo":
            st.session_state[f"{key_prefix}/edit_nuget_set"] = _move_pointer("undo")
        elif action == "redo":
            st.session_state[f"{key_prefix}/edit_nuget_set"] = _move_pointer("redo")
        elif action == "restart":
            st.session_state[f"{key_prefix}/edit_nuget_set"] = nugget_loader.get(current_topic, source=st.session_state[f"{key_prefix}/source"])
            _push_new_action(st.session_state[f"{key_prefix}/edit_nuget_set"].clone())
        

    st.write(f"## Topic {current_topic}")
    column_ratio = [4,6]

    title_left, title_right = st.columns(column_ratio)
    title_left.write("**Raw Nugget Viewer (Frozen)**")
    title_right.write(":orange[**Nugget Editor**]")


    session_set_default(f"{key_prefix}/source", "json")
    def _on_select_source():
        selection = st.session_state[f"{key_prefix}/source_selector"]
        if selection == "raw":
            st.session_state[f"{key_prefix}/source"] = "json"
        elif selection == "saved_revised":
            st.session_state[f"{key_prefix}/source"] = "revised"


    source_sel_col, action_col = st.columns(column_ratio, vertical_alignment="center")
    source_sel_col.selectbox(
        "select_source",
        options=["raw", "saved_revised"],
        format_func=lambda x: " ".join(x.split("_") + ["nuggets"]).title(),
        index=0,
        key=f"{key_prefix}/source_selector",
        label_visibility="collapsed",
        on_change=_on_select_source
    )

    action_col.segmented_control(
        "actions", 
        options=["undo", "restart", "save", "redo"],
        format_func={
            "undo": ":material/undo: Undo", 
            "redo": ":material/redo: Redo", 
            "restart": ":material/refresh: Reload From Left",
            "save": ":material/save: Save"
        }.__getitem__,
        selection_mode="single",
        label_visibility="collapsed",
        key=f"{key_prefix}/action_btn",
        on_change=_on_select_action
    )

    source_col, editor_col = st.columns(column_ratio)

    source_nugget_set = nugget_loader.get(current_topic, source=st.session_state[f"{key_prefix}/source"])

    with source_col:
        draw_nugget_editor(
            source_nugget_set,
            current_doc_id="_post_hoc_edit_",
            key_prefix=f'{key_prefix}/source_nugget_viewer',
            highlight_group_name=False,
            allow_nugget_answer_selection=False,
            allow_nugget_answer_creation=False,
            allow_nugget_question_creation=False,
            allow_nugget_group_edit=False,
            allow_nugget_question_edit=False,
        )

    def _init_nugget():
        _push_new_action(source_nugget_set.clone())
        return source_nugget_set.clone()

    session_set_default(f"{key_prefix}/edit_nuget_set", _init_nugget)
    edit_nuget_set: NuggetSet = st.session_state[f"{key_prefix}/edit_nuget_set"]


    @st.dialog(title="Rewrite Or Delete Answer")
    def _rewrite_answer_modal(doc_id, question, answers):
        assert len(answers) == 1
        old_answer = answers[0]

        st.write(f"Old answer: **{old_answer}**")
        
        
        new_answer = st.text_input(label="New answer", key=f"{key_prefix}/rewrite_answer/new_answer")

        changed = False
        left_col, _, right_col = st.columns(3)
        if left_col.button(label="Rewrite", use_container_width=True):
            edit_nuget_set.rewrite_answer(question, old_answer, new_answer)
            changed = True

        if right_col.button(label="Delete", use_container_width=True):
            edit_nuget_set.remove_answer(question, old_answer)
            changed = True


        if changed:
            _push_new_action(edit_nuget_set.clone())

            for key in st.session_state.keys():
                if key.startswith(f"{key_prefix}/nugget_editor/nugget/") and key.endswith("/select"):
                    del st.session_state[key]
            
            st.rerun()
    

    def _on_select_nugget_answer(doc_id, question, answers):
        _rewrite_answer_modal(doc_id, question, answers)
        
        # return True
        # assert len(answers) == 1
        # edit_nuget_set.remove_answer(question, answers[0])
        # _push_new_action(edit_nuget_set.clone())

    def _on_assign_group(question, group_name):
        edit_nuget_set.set_group(question, group_name)
        _push_new_action(edit_nuget_set.clone())

    def _on_rename_group(old_group_name, new_group_name):
        edit_nuget_set.rename_group(old_group_name, new_group_name)
        _push_new_action(edit_nuget_set.clone())
    
    def _on_rewrite_question(old_question, new_question):
        edit_nuget_set.rewrite_question(old_question, new_question)
        _push_new_action(edit_nuget_set.clone())

    with editor_col:
        draw_nugget_editor(
            edit_nuget_set, 
            current_doc_id="_post_hoc_edit_",
            key_prefix=f'{key_prefix}/nugget_editor',
            allow_nugget_answer_selection=True,
            allow_nugget_answer_creation=False,
            allow_nugget_question_creation=False,
            allow_nugget_group_edit=True,
            allow_nugget_question_edit=True,
            on_select_nugget_answer=_rewrite_answer_modal,
            on_assign_group=_on_assign_group,
            on_rename_group=_on_rename_group,
            on_rewrite_question=_on_rewrite_question
        )