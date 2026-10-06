"""JobsTracker dashboard. Run from backend/:  streamlit run dashboard.py"""
import streamlit as st

st.set_page_config(page_title="JobsTracker", page_icon="🌿", layout="wide")

page = st.navigation(
    [
        st.Page("app_pages/overview.py", title="Overview", icon=":material/wb_sunny:", default=True),
        st.Page("app_pages/applications.py", title="Applications", icon=":material/table_view:"),
        st.Page("app_pages/label.py", title="Label emails", icon=":material/label:"),
    ],
    position="top",
)
page.run()
