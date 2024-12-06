import uuid
from argparse import ArgumentParser
from pathlib import Path
import pandas as pd

import streamlit as st
from streamlit.runtime.state import get_session_state
from page_utils import random_key, draw_pages, stpage, goto_page, get_auth_manager, AuthManager

from task_resources import TaskConfig
from data_manager import initialize_managers, SentenceAnnotationManager, get_manager, session_set_default


_style_modifier = """
<style>
[data-testid="stMainBlockContainer"] {
    padding: 6rem 2rem 0rem
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
from stage_citaiton_assessment import citation_assessment_page
from stage_report_annotation import report_annotation_page


@stpage(name='login')
def login_page(auth_manager: AuthManager):
    
    _, col, _ = st.columns([1, 1, 1])
    with col.form("my_form"):
        st.write("## Login")
        if 'logout_message' in st.session_state and st.session_state['logout_message'] is not None:
            st.info(st.session_state['logout_message'])
            st.session_state['logout_message'] = None

        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button('Login', type='primary')

    if submit and auth_manager.login(username, password):
        st.rerun()

@st.dialog("Change Password")
def change_password_modal(auth_manager: AuthManager, logout_fn):
    
    old_password = st.text_input("Old Password", type="password")
    new_password = st.text_input("New Password", type="password")
    re_new_password = st.text_input("Retype New Password", type="password")

    if st.button("Submit", type="primary", key=random_key()):
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


    
@stpage(name='task_dashboard', require_login=True)
def task_dashboard(auth_manager: AuthManager):
    # st.write(f"# Task Dashboard")

    if 'task' not in st.query_params:
        st.success("Select a task first", icon=':material/west:')

    else:
        task_name = st.query_params['task']
        task_config: TaskConfig = st.session_state['task_configs'][ task_name ]

        user_topics = task_config.job_assignment.get( auth_manager.current_user, [] )

        initialize_managers(task_config, auth_manager.current_user)

        st.write(f"## {task_name}")

        st.write("### Citation Assessments and Support")

        def _jump(page, topic_id):
            st.session_state['sidebar_state'] = "collapsed"
            st.query_params.topic = topic_id
            st.query_params.page = page

        citation_assess_topics = sorted(filter(lambda x: x in user_topics, task_config.cited_sentences.keys()))
        citation_assessment_manager: SentenceAnnotationManager = get_manager(task_config, 'citation_assessment_manager')
        for topic_id, col in zip(citation_assess_topics, st.columns(8)):

            n_done = citation_assessment_manager.count_done(topic_id, level='doc_id')
            # n_job = len(task_config.cited_sentences[topic_id])
            n_job = citation_assessment_manager.count_job(topic_id, level='doc_id')
            icon = ':material/check_box_outline_blank:' if not citation_assessment_manager.is_all_done(topic_id) else ':material/select_check_box:'
            col.button(
                f"Topic {topic_id} ({n_done}/{n_job})", 
                icon=icon,
                use_container_width=True, 
                args=("citation_assessment", ), 
                kwargs={'topic': topic_id, "collapse_sidebar": True},
                on_click=goto_page
            )
    
        # force_citation_asssessment_before_report
        st.write("### Report Sentence Assessments")
        if task_config.force_citation_asssessment_before_report:
            st.caption("Can only start assessing report sentences after citation assessments are finished.")
        report_annotation_topics = sorted(filter(lambda x: x in user_topics, task_config.report_runs.keys()))
        report_annotation_manager: SentenceAnnotationManager = get_manager(task_config, 'report_annotation_manager')
        for topic_id, col in zip(report_annotation_topics, st.columns(8)):
            
            # TODO: disable ones that haven't finished citation assessments
            icon = ':material/check_box_outline_blank:' if not report_annotation_manager.is_all_done(topic_id) else ':material/select_check_box:'
            n_done = report_annotation_manager.count_done(topic_id, level='run_id')
            n_job = report_annotation_manager.count_job(topic_id, level='run_id')
            activated = not task_config.force_citation_asssessment_before_report or citation_assessment_manager.is_all_done(topic_id)
            col.button(
                f"Topic {topic_id} ({n_done}/{n_job})", 
                icon=icon,
                use_container_width=True, 
                disabled=not activated,
                args=("report_annotation", ), 
                kwargs={'topic': topic_id, "collapse_sidebar": True},
                on_click=goto_page
            )


def draw_sidebar():

    def logout(message=None):
        st.session_state['logout_message'] = message
        auth_manager.logout()
        st.query_params.clear()

    with st.sidebar:
        st.write("## RAG Annotation Protal")

        if auth_manager.current_user is not None:

            for task_name in task_configs.keys():
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
        



if __name__ == '__main__':

    parser = ArgumentParser()
    parser.add_argument('--user_db_path', type=Path, default="./user_db.db")
    parser.add_argument('--task_configs', nargs='+', type=Path, default=[])

    args = parser.parse_args()

    auth_manager = init_app(args)

    # TODO make this dynamic, with a flag
    task_configs = {}
    for config in map(TaskConfig.from_json, args.task_configs):
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
