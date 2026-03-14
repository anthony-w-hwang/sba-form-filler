import streamlit as st

st.set_page_config(
    page_title="SBA Prequal — Form",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)

with st.sidebar:
    st.markdown(
        '<a href="/" target="_self" style="display:inline-block;color:#374151;font-size:13px;font-weight:500;text-decoration:none;padding:8px 12px;background:#fff;border:1px solid #D1D5DB;border-radius:7px;width:100%;box-sizing:border-box">← Back to Loan Officer Dashboard</a>',
        unsafe_allow_html=True,
    )

st.markdown(
    '<iframe src="https://anthony-w-hwang.github.io/sba-prequal/prequal.html" '
    'width="100%" height="900" style="border:none;border-radius:12px;"></iframe>',
    unsafe_allow_html=True,
)
