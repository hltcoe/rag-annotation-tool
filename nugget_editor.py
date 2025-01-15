from typing import Callable

import streamlit as st

from page_utils import toggle_button, random_key
from data_manager import NuggetSet


# @st.fragment()
def draw_nugget_editor(
        nugget_set: NuggetSet, current_doc_id: str, key_prefix: str,
        title: str = None,
        show_counts: bool = True,
        on_select_nugget_answer: Callable=None, on_unselect_nugget_answer: Callable=None,
        on_assign_group: Callable=None, on_rename_group: Callable=None,
        on_rewrite_question: Callable=None,
        highlight_group_name: bool = True,
        allow_nugget_answer_selection: bool = True,
        allow_nugget_answer_creation: bool = True,
        allow_nugget_question_creation: bool = True,
        allow_nugget_group_edit: bool = True,
        allow_nugget_question_edit: bool = False
    ):

    def _modify_answer(nidx, selection_key, add_key = None):
        if not allow_nugget_answer_selection:
            st.session_state[selection_key] = []
            return
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
                # print(set(answers) - original_selected)
                assert len(set(answers) - original_selected) == 0, "You can't do delete and add at the same time..."

                if on_unselect_nugget_answer:
                    on_unselect_nugget_answer(current_doc_id, question, deleted)
                    return
                
        # Adding
        success = None
        if on_select_nugget_answer:
            success = on_select_nugget_answer(current_doc_id, question, answers)
            
        if success is None or success:
            del st.session_state[selection_key]
            if add_key is not None:
                del st.session_state[add_key]
        
        st.rerun()
    
    def _modify_question(nidx, text_key, toggle_key):
        old_question = nugget_set[nidx][0]
        new_question = st.session_state[text_key]

        if old_question != new_question and on_rewrite_question:
            on_rewrite_question(old_question, new_question)
    
        st.session_state[toggle_key] = False


    @st.dialog("Rename Group")
    def rename_group_modal(old_name):
        st.write(f"Rename group `{old_name}` as")
        with st.form("rename_group"):
            new_name = st.text_input("New Group Name")
            if new_name == "default":
                st.error("Cannot use the name default -- select `default` instead")
            if st.form_submit_button("Submit", type="primary") and new_name is not None:
                if on_rename_group is not None:
                    on_rename_group(old_name, new_name)
                st.rerun()

    @st.dialog("New Group")
    def new_group_modal(nugget_question):
        with st.form("new_group"):
            group_name = st.text_input("New Group Name")
            if st.form_submit_button("Submit", type="primary"):
                if on_assign_group is not None:
                    on_assign_group(nugget_question, group_name)        
                st.rerun()

    _new_group_label = "+ New Group"
    def _select_group(key, nugget_question):
        selected_val = st.session_state[key]
        if _new_group_label == selected_val:
            new_group_modal(nugget_question)
        elif on_assign_group is not None:
            on_assign_group(nugget_question, selected_val)

    if title is not None:
        st.write(f"**{title}**")

    sorted_nugget_groups = nugget_set.groups + [_new_group_label]
    # print(nugget_set.group_assignment)

    # for nidx, question, a_dict in nugget_set.iter_nuggets():
    for group_name, nugget_members in nugget_set.iter_grouped_nuggets():
        group_container = st.container(border=True)
        if group_name != "default":
            if allow_nugget_group_edit:
                name_col, change_col = group_container.columns([5.5,1.5], vertical_alignment='center')
            else:
                name_col, change_col = *group_container.columns([1], vertical_alignment='center'), None
            
            name_col.write(f":orange[Group: {group_name}]" if highlight_group_name else f"Group: {group_name}")
            
            if allow_nugget_group_edit and \
               change_col.button("Rename", icon=":material/edit:", key=f"{key_prefix}/group/{group_name}/rename"):
                rename_group_modal(group_name)

        skipped_first = False
        for nidx, question, a_dict in nugget_members:
            if skipped_first:
                group_container.html('<hr class="nugget_set_divider">')
            skipped_first = True

            need_new_answer_column = allow_nugget_answer_creation \
                and f"{key_prefix}/nugget/{nidx}/select" in st.session_state \
                and '+' in st.session_state[f"{key_prefix}/nugget/{nidx}/select"]

            if need_new_answer_column and allow_nugget_group_edit:
                q_col, a_col, input_col, group_col = group_container.columns([2,2,1.5,1.5], vertical_alignment='center')
            elif allow_nugget_group_edit:
                q_col, a_col, group_col = group_container.columns([2,3.5,1.5], vertical_alignment='center')
            elif need_new_answer_column:
                q_col, a_col, input_col = group_container.columns([2,2,3], vertical_alignment='center')
            else:
                q_col, a_col = group_container.columns([5,5], vertical_alignment='center')
            
            

            if allow_nugget_question_edit:
                if q_col.toggle(question, key=f"{key_prefix}/nugget/{nidx}/question_toggle"):
                    q_col.text_input(
                        label="q_edit",
                        value=question, 
                        key=f"{key_prefix}/nugget/{nidx}/question_edit",
                        label_visibility="collapsed",
                        args=(nidx, f"{key_prefix}/nugget/{nidx}/question_edit", f"{key_prefix}/nugget/{nidx}/question_toggle"),
                        on_change=_modify_question
                    )
            else:
                q_col.write(question)
                
            def _display_answers(k):
                if k == "+":
                    return ":material/add:"
                if show_counts:
                    return f"{k} ({len(a_dict[k])})"
                return k
            
            selected_answers = [ a for a, dids in a_dict.items() if current_doc_id in dids ]
            answer_selection = a_col.pills(
                label="answers", 
                options=sorted(a_dict.keys()) + (["+"] if allow_nugget_answer_creation else []),
                format_func=_display_answers,
                default=selected_answers,
                selection_mode='multi',
                label_visibility='collapsed',
                key=f"{key_prefix}/nugget/{nidx}/select",
                # args=(nidx, f"{key_prefix}/nugget/{nidx}/select"),
                # on_change=_modify_answer
            )
            if set(answer_selection) != set(selected_answers):
                _modify_answer(nidx, f"{key_prefix}/nugget/{nidx}/select")

            if  "+" in answer_selection:
                input_col.text_input(
                    label="add_answer",
                    placeholder="New answer...",
                    key=f"{key_prefix}/nugget/{nidx}/add",
                    label_visibility='collapsed',
                    args=(nidx, f"{key_prefix}/nugget/{nidx}/select", f"{key_prefix}/nugget/{nidx}/add"),
                    on_change=_modify_answer
                )
            
            group_key = f"{key_prefix}/nugget/{nidx}/group"
            if allow_nugget_group_edit:
                group_col.selectbox(
                    label="select_group",
                    options=sorted_nugget_groups,
                    index=sorted_nugget_groups.index(group_name),
                    key=group_key,
                    label_visibility="collapsed",
                    args=(group_key, question),
                    on_change=_select_group
                )
            
        


    def _new_nugget():
        question = st.session_state[f"{key_prefix}/nugget/new/question"]
        answer = st.session_state[f"{key_prefix}/nugget/new/answer"]
        if question is None or question == "" or answer is None or answer == "":
            return
        
        success = None
        if on_select_nugget_answer:
            success = on_select_nugget_answer(current_doc_id, question, [answer])
        if success is None or success == True:
            st.session_state[f"{key_prefix}/nugget/new/question"] = ""
            st.session_state[f"{key_prefix}/nugget/new/answer"] = ""
            st.session_state[f"{key_prefix}/nugget/new/toggle"] = False

    
    if allow_nugget_question_creation and toggle_button("Add New Nugget Question", key=f"{key_prefix}/nugget/new/toggle"):

        # add new nugget
        q_add_col, a_add_col, g_add_col = st.columns([2,3.5,1.5], vertical_alignment='center')
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
        # g_add_col.selectbox(
        #     label="select_group",
        #     options=["Default Group"],
        #     key=f"{key_prefix}/nugget/new/group",
        #     label_visibility="collapsed"
        # )
