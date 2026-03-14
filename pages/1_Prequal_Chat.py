import streamlit as st
import os

st.set_page_config(
    page_title="SBA Prequal — AI Chat",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

with st.sidebar:
    st.markdown(
        '<a href="/" target="_self" style="display:inline-block;color:#374151;font-size:13px;font-weight:500;text-decoration:none;padding:8px 12px;background:#fff;border:1px solid #D1D5DB;border-radius:7px;width:100%;box-sizing:border-box">← Back to Loan Officer Dashboard</a>',
        unsafe_allow_html=True,
    )

html_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prequal_chat.html")
with open(html_path, "r") as f:
    html_content = f.read()

st.components.v1.html(html_content, height=900, scrolling=True)
