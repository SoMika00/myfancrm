import os
import streamlit as st

from app.db import init_db

st.set_page_config(page_title="MyFanCRM", layout="wide")

init_db()

st.sidebar.header("MyFanCRM")
api_url = st.sidebar.text_input(
    "URL API Sinhome_llm",
    value=st.session_state.get("api_url")
    or os.environ.get("SINHOME_API_URL")
    or "http://127.0.0.1:8000",
)
st.session_state["api_url"] = api_url

st.sidebar.caption("Endpoints: /personality_chat, /script_chat, /script_media")

st.title("MyFanCRM")
st.write("Utilise le menu 'Pages' de Streamlit pour naviguer.")
