import logging
 
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
 
from src.alita_sdk.utils.streamlit import run_streamlit
 
try:
    import streamlit as st
except ImportError:
    logger.error("Streamlit not found, please install it using `pip install streamlit`")
    exit(1)

if 'messages' not in st.session_state:
    st.session_state.messages = []
    st.session_state.thread_id = None
    st.session_state.agent_executor = None
    st.session_state.llm = None
    st.session_state.agent_name = "Load agent using config"
    st.session_state.agents = []
    st.session_state.models = []

run_streamlit(st)