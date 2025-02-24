from argparse import ArgumentParser
from pathlib import Path
from datetime import datetime
from typing import Dict
import pandas as pd

from itertools import cycle

import streamlit as st
from page_utils import random_key, draw_pages, stpage, goto_page, get_auth_manager, AuthManager

from task_resources import TaskConfig
from data_manager import AnnotationManager, get_manager, get_nugget_loader, session_set_default, export_data


_style_modifier = """
<style>
header:has(.stAppToolbar) {
    height: 0px;
}

[data-testid="stMainBlockContainer"] {
    padding: 2rem 2rem 4rem
}

[data-testid="stVerticalBlockBorderWrapper"]:has(.is_done_flag) {
    border-color: green; 
    border-width: 2px
}

[data-testid="stVerticalBlockBorderWrapper"][height]:has(.fake_button_container) button {
    border-width: 0px;
    text-align: left;
}

.st-key-sentence_selection button {
    justify-content: left;
    text-align: left;
}

button[kind="pills"] {
    overflow: unset;
    white-space: unset;
    text-overflow: unset; 
    height: unset;
    border-radius: 20px;
    text-align: left;
}

[data-testid="stElementContainer"]:has(hr.nugget_set_divider) {
    margin-top: -35px; 
    margin-bottom: -35px;
}



</style>
"""

# Do this before importing each pages
def init_app(args):

    if 'sidebar_state' not in st.session_state or st.session_state['sidebar_state'] not in ['auto', 'expanded', 'collapsed']:
        st.session_state['sidebar_state'] = "auto"

    st.set_page_config(
        page_title="RAG Annotation Tool",
        page_icon=":material/flaky:",
        initial_sidebar_state=st.session_state['sidebar_state'],
        layout="wide",
        menu_items={
            # 'Get Help': 'https://www.extremelycoolapp.com/help',
            # 'Report a bug': "https://www.extremelycoolapp.com/bug",
            # 'About': "# This is a header. This is an *extremely* cool app!"
        }
    )

    st.html(_style_modifier)

    return get_auth_manager(args.user_db_path)


# just import should be fine...
from stage_nugget_creation import nugget_creation_page
from stage_citaiton_assessment import citation_assessment_page
from stage_nugget_revision import nugget_revision_page
from stage_nugget_alignment import nugget_alignment_page


@stpage(name='login')
def login_page(auth_manager: AuthManager):
    
    # _, col, _ = st.columns([1, 1, 1])
    @st.dialog(title="Login")
    def login_modal():
        with st.form("my_form"):
            # st.write("## Login")
            if 'logout_message' in st.session_state and st.session_state['logout_message'] is not None:
                st.info(st.session_state['logout_message'])
                st.session_state['logout_message'] = None

            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button('Login', type='primary')

        if submit and auth_manager.login(username, password):
            st.rerun()
    
    if auth_manager.current_user is None:
        login_modal()

@st.dialog("Change Password")
def change_password_modal(auth_manager: AuthManager, logout_fn):
    
    old_password = st.text_input("Old Password", type="password")
    new_password = st.text_input("New Password", type="password")
    re_new_password = st.text_input("Retype New Password", type="password")

    if st.button("Submit", type="primary", key="change_password_form"):
        if new_password != re_new_password:
            st.error("Inconsistent new passwords")
        if auth_manager.change_password(old_password, new_password):
            logout_fn("Password changed. Please login again.")
            st.rerun()
        

@stpage(name="manage_users", require_login=True, require_admin=True)
def manage_users_page(auth_manager: AuthManager):

    # weird hack
    session_set_default('new_user_df_uuid', random_key)
    
    st.write("## User Management")

    st.write("### Batch Adding Users")

    existing_users = auth_manager.get_all_users()

    warning_container = st.container()

    new_user_df = st.data_editor(
        pd.DataFrame({
            'username': pd.Series(dtype=str), 
            'password': pd.Series(dtype=str), 
            'admin': pd.Series(dtype=bool)
        }),
        column_config={
            "username": st.column_config.TextColumn(
                "Username", required=True,
            ),
            "password": st.column_config.TextColumn(
                "Password", default="MyFancy23CharPassword!!", required=True,
            ),
            "admin": st.column_config.CheckboxColumn(
                "Admin?", default=False
            )
        },
        key=st.session_state['new_user_df_uuid'],
        num_rows='dynamic',
        use_container_width=True
    )

    @st.dialog("Confirm Adding Users")
    def _confirm():
        st.pills(
            "Adding normal users:",
            options=new_user_df[new_user_df.admin == False]['username'].to_list(),
            key="testa"
        )
        st.pills(
            "Adding **power** users:",
            options=new_user_df[new_user_df.admin == True]['username'].to_list(),
            key="testb"
        )

        if st.button("Confirm", type="primary", key=random_key):
            st.session_state['new_user_df_uuid'] = random_key()
            for info in new_user_df.T.to_dict().values():
                auth_manager.add_user(**info)
            
            st.rerun()

    if st.button("Submit", type="primary"):
        overlap = set(new_user_df.username.tolist()) & set(u for u, _ in existing_users)
        if len(overlap) > 0:
            warning_container.warning(
                ", ".join(overlap) + " already exist."
            )
        elif len(set(new_user_df.username.tolist())) > 0:
            _confirm()

    
    @st.dialog("Confirm Deleting User")
    def _delete_user(username):
        st.write(f"Are you sure you want to delete user `{username}`?")

        if st.button("Confirm", type='primary', key=random_key):
            auth_manager.delete_user(username)
            st.session_state['delete_user'] = None
            st.rerun()

    st.write("### Delete Users")

    delete_selection = st.pills(
        "**Existing Users**",
        options=[
            (":material/bolt: " if is_admin else "") + str(username)
            for username, is_admin in existing_users
        ],
        selection_mode='single',
        key="delete_user", 
        label_visibility='collapsed'
    )

    if delete_selection is not None:
        _delete_user(delete_selection.replace(":material/bolt: ", ""))

@st.dialog(title="Download")
def export_modal(task_config: TaskConfig, username: str):
    # making this a modal to prevent creating the zip file everytime 
    # someone arrive at the dashboard
    print("running export")
    buffer = export_data(task_config, username, [
        "relevance_assessment_manager",
        "citation_assessment_manager",
        "nugget_alignment_manager",
    ], with_revised_nuggets=True, with_annotator_nuggets=True)

    st.download_button(
        label="Download",
        data=buffer,
        file_name=f"{task_config.name}_{datetime.now().isoformat()}_export.zip", 
        mime="application/zip"
    )

    
@stpage(name='task_dashboard', require_login=True)
def task_dashboard(auth_manager: AuthManager):
    # st.write(f"# Task Dashboard")

    if 'task' not in st.query_params:
        st.success("Select a task first", icon=':material/west:')

    else:
        task_name = st.query_params['task']
        task_config: TaskConfig = st.session_state['task_configs'][ task_name ]

        user_topics = task_config.job_assignment.get( auth_manager.current_user, [] )

        # initialize_managers(task_config, auth_manager.current_user)

        title_col, button_col = st.columns([6, 1], vertical_alignment="center")
        title_col.write(f"## {task_name}")
        if auth_manager.is_admin and button_col.button("Export Data", use_container_width=True):
            export_modal(task_config, auth_manager.current_user)

        st.write("### Step 1: Nugget Creation")

        # TODO change the ordering
        relevance_assess_topics = [ t for t in user_topics if t in task_config.pooled_docs.keys() ]
        # sorted(filter(lambda x: x in user_topics, task_config.pooled_docs.keys()))
        relevance_assessment_manager: AnnotationManager = get_manager(task_config, auth_manager.current_user, 'relevance_assessment_manager')
        for topic_id, col in zip(relevance_assess_topics, cycle(st.columns(6))):

            n_done = relevance_assessment_manager.count_done(topic_id, level='doc_id')
            # n_job = len(task_config.cited_sentences[topic_id])
            n_job = relevance_assessment_manager.count_job(topic_id, level='doc_id')
            icon = ':material/check_box_outline_blank:' if not relevance_assessment_manager.is_all_done(topic_id) else ':material/select_check_box:'
            col.button(
                f"Topic {topic_id} ({n_done}/{n_job})", 
                icon=icon,
                use_container_width=True, 
                key=f'{task_config.name}/entry/creation/{topic_id}',
                args=("nugget_creation", ), 
                kwargs={'topic': topic_id, "collapse_sidebar": True},
                on_click=goto_page
            )


        if auth_manager.is_admin:
            st.write("### Step 2: Nugget Revision (Admin Only)")
            all_loaded_topics = list(set([ t for ts in task_config.job_assignment.values() for t in ts ]))
            for topic_id, col in zip(sorted(all_loaded_topics), cycle(st.columns(6))):
                col.button(
                    f"Topic {topic_id}",
                    use_container_width=True, 
                    args=("nugget_revision", ), 
                    key=f'{task_config.name}/entry/revision/{topic_id}',
                    kwargs={'topic': topic_id, "collapse_sidebar": True},
                    on_click=goto_page
                )


        st.write("### Step 3: Report Sentence and Nugget Support Assessment")

        citation_assess_topics = [ t for t in user_topics if task_config.cited_sentences.keys() ]
        # sorted(filter(lambda x: x in user_topics, task_config.cited_sentences.keys()))
        citation_assessment_manager: AnnotationManager = get_manager(task_config, auth_manager.current_user, 'citation_assessment_manager')
        for topic_id, col in zip(citation_assess_topics, cycle(st.columns(6))):

            n_done = min(
                citation_assessment_manager.count_done(topic_id, level='doc_id'), 
                relevance_assessment_manager.count_done(topic_id, level='doc_id')
            )
            # n_job = len(task_config.cited_sentences[topic_id])
            n_job = citation_assessment_manager.count_job(topic_id, level='doc_id')
            icon = ':material/check_box_outline_blank:' if not citation_assessment_manager.is_all_done(topic_id) else ':material/select_check_box:'
            col.button(
                f"Topic {topic_id} ({n_done}/{n_job})", 
                icon=icon,
                use_container_width=True, 
                key=f'{task_config.name}/entry/supportive/{topic_id}',
                args=("citation_assessment", ), 
                kwargs={'topic': topic_id, "collapse_sidebar": True},
                on_click=goto_page
            )
    
        # force_citation_asssessment_before_report
        st.write("### Step 4: Nugget Alignment")
        if task_config.force_citation_asssessment_before_report:
            st.caption("Can only start assessing report sentences for nugget alignment after report sentnece supportive assessments are finished.")
        nugget_alignment_topics = [ t for t in user_topics if t in task_config.report_runs.keys() ]
        # sorted(filter(lambda x: x in user_topics, task_config.report_runs.keys()))
        nugget_alignment_manager: AnnotationManager = get_manager(task_config, auth_manager.current_user, 'nugget_alignment_manager')
        nugget_loader = get_nugget_loader(
            task_config, auth_manager.current_user, use_revised_nugget=task_config.use_revised_nugget_only
        )
        for topic_id, col in zip(nugget_alignment_topics, cycle(st.columns(6))):
            icon = ':material/check_box_outline_blank:' if not nugget_alignment_manager.is_all_done(topic_id) else ':material/select_check_box:'
            n_done = nugget_alignment_manager.count_done(topic_id, level='run_id')
            n_job = nugget_alignment_manager.count_job(topic_id, level='run_id')
            activated = not task_config.force_citation_asssessment_before_report or citation_assessment_manager.is_all_done(topic_id)

            if task_config.use_revised_nugget_only:
                activated = activated and len(nugget_loader[topic_id]) > 0

            col.button(
                f"Topic {topic_id} ({n_done}/{n_job})", 
                icon=icon,
                use_container_width=True, 
                key=f'{task_config.name}/entry/alignment/{topic_id}',
                disabled=not activated,
                args=("nugget_alignment", ), 
                kwargs={'topic': topic_id, "collapse_sidebar": True},
                on_click=goto_page
            )
        



def draw_sidebar():

    def logout(message=None):
        st.session_state['logout_message'] = message
        auth_manager.logout()
        st.query_params.clear()

    with st.sidebar:
        st.write("## RAG Annotation Portal")

        if auth_manager.current_user is not None:

            for task_name, task_config in task_configs.items():
                if len(task_config.job_assignment.get(auth_manager.current_user, [])) == 0:
                    continue
                
                if st.button(f"{task_name}"):
                    st.query_params['task'] = task_name
                    st.query_params.page = "task_dashboard"
            
            if auth_manager.is_admin:
                st.divider()
                st.button(
                    f"User Management", 
                    icon=":material/group_add:",
                    args=("manage_users", ), 
                    on_click=goto_page
                )
                
                # st.write(auth_manager.session_user_mapping)
            
            st.divider()
            
            if st.button("Change Password", icon=":material/password:"):
                change_password_modal(auth_manager, logout)

            st.button("Logout", icon=":material/logout:", on_click=logout)
        
        else:
            st.button("Login", icon=":material/login:", args=("login", ), on_click=goto_page)



if __name__ == '__main__':

    parser = ArgumentParser()
    parser.add_argument('--user_db_path', type=Path, default="./user_db.db")
    # parser.add_argument('--task_configs', nargs='+', type=Path, default=[])
    parser.add_argument('--task_config_path', type=str, default="./configs")

    args = parser.parse_args()

    auth_manager = init_app(args)

    # TODO make this dynamic, with a flag
    task_configs: Dict[str, TaskConfig] = {}
    for config in map(TaskConfig.from_json, Path(args.task_config_path).glob("*.json")):
        assert config.name not in task_configs, f"Task Name Collision -- {config.name}"
        task_configs[config.name] = config
    
    st.session_state['task_configs'] = task_configs

    for config in task_configs.values():
        Path(config.output_dir).mkdir(parents=True, exist_ok=True)

    draw_sidebar()

    draw_pages(
        db_path=args.user_db_path,
        get_param='page',
        default_page='task_dashboard'
    )
