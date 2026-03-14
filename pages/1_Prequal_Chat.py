import streamlit as st
import os

st.set_page_config(
    page_title="SBA Prequal — AI Chat",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

with st.sidebar:
    if st.button("← Back to Loan Officer Dashboard", use_container_width=True):
        st.switch_page("app_lo.py")

html_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prequal_chat.html")
with open(html_path, "r") as f:
    html_content = f.read()

st.components.v1.html(html_content, height=900, scrolling=True)
