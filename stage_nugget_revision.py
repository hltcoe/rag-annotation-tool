import streamlit as st
import pandas as pd
from pathlib import Path

from page_utils import stpage, draw_bread_crumb, toggle_button, get_auth_manager, random_key, AuthManager

from task_resources import TaskConfig
from data_manager import NuggetSaverManager, NuggetSet, SentenceAnnotationManager, initialize_managers, get_nugget_viewer
import ir_datasets as irds


@stpage("nugget_revision", require_login=True, require_admin=True)
@st.fragment
def nugget_revision_page(auth_manager: AuthManager):
    if 'topic' not in st.query_params:
        st.query_params.clear()
    
    current_topic = st.query_params['topic']
    task_config: TaskConfig = st.session_state['task_configs'][st.query_params['task']]
    # initialize_managers(task_config, auth_manager.current_user)


    st.write(f"Topic {current_topic}")

    nugget_viewer = get_nugget_viewer(
        task_config, auth_manager.current_user, from_all_users=True, use_revised_nugget=False
    )

    st.write(nugget_viewer[current_topic].as_dataframe())