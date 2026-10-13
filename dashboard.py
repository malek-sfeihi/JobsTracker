"""JobsTracker dashboard. Run from backend/:  streamlit run dashboard.py"""
import streamlit as st

from app.core.config import settings

st.set_page_config(page_title="JobsTracker", page_icon="🌿", layout="wide")


def login_configured() -> bool:
    """True online (an [auth] section exists in the Streamlit secrets), False on your PC."""
    try:
        return "auth" in st.secrets
    except Exception:  # no secrets file at all: local use, no login needed
        return False


# Online, the dashboard holds your emails: only your Google account may open it
if login_configured():
    if not st.user.get("is_logged_in", False):
        st.title("🌿 JobsTracker")
        st.write("This dashboard is private.")
        st.button("Sign in with Google", icon=":material/login:", on_click=st.login, type="primary")
        st.stop()
    if not settings.allowed_email or st.user.email.lower() != settings.allowed_email.lower():
        st.error(f"{st.user.email} is not allowed to open this dashboard.", icon=":material/block:")
        st.button("Sign out", on_click=st.logout)
        st.stop()

page = st.navigation(
    [
        st.Page("app_pages/overview.py", title="Overview", icon=":material/wb_sunny:", default=True),
        st.Page("app_pages/applications.py", title="Applications", icon=":material/table_view:"),
        st.Page("app_pages/label.py", title="Label emails", icon=":material/label:"),
    ],
    position="top",
)
page.run()
