"""Applications page: every application in detail, with its full email timeline."""
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from app.core.config import settings
from app.db.database import get_connection
from app.filters.reasons import REASON_LABELS
from app.ui import CATEGORY_LABELS, STATUS_LABELS, nice_name

conn = get_connection()
apps = pd.read_sql("SELECT * FROM applications", conn)
emails = pd.read_sql(
    "SELECT id, application_id, received_at, category, sender, subject FROM emails "
    "WHERE application_id IS NOT NULL ORDER BY received_at",
    conn,
)
conn.close()

st.header("Applications")
if apps.empty:
    st.info("No applications yet. Sync with Gmail from the Overview page.")
    st.stop()

now = datetime.now(timezone.utc)
emails["received_at"] = pd.to_datetime(emails["received_at"], utc=True, format="ISO8601")
for column in ("first_activity", "last_activity"):
    apps[column] = pd.to_datetime(apps[column], utc=True, format="ISO8601")

# The company's first answer = its first email that isn't just "we received your application"
answers = emails[emails["category"] != "confirmation"].groupby("application_id").first()
apps = apps.join(answers[["received_at", "category"]].rename(
    columns={"received_at": "answered_at", "category": "answer"}), on="id")
apps["email_count"] = apps["id"].map(emails.groupby("application_id").size()).fillna(0).astype(int)

table = pd.DataFrame({
    "Company": apps["company"].map(nice_name),
    "Position": apps["position"].fillna(""),
    "Type": apps["kind"],
    "Applied": apps["first_activity"].dt.tz_convert(None),
    "Status": apps["status"].map(STATUS_LABELS),
    "First answer": apps["answer"].map(CATEGORY_LABELS).fillna("No answer yet"),
    "Answered on": apps["answered_at"].dt.tz_convert(None),
    "Days to answer": (apps["answered_at"] - apps["first_activity"]).dt.days,
    "Days since last news": (now - apps["last_activity"]).dt.days,
    "Rejection reason": apps["rejection_reason"].map(REASON_LABELS).fillna(""),
    "What they wrote": apps["rejection_quote"].fillna(""),
    "Emails": apps["email_count"],
    "id": apps["id"],
}).sort_values("Applied", ascending=False)

# ---------------------------------------------------------------- filters
with st.container(horizontal=True, vertical_alignment="bottom"):
    statuses = st.pills("Status", list(STATUS_LABELS.values()), selection_mode="multi",
                        default=list(STATUS_LABELS.values()))
    search = st.text_input("Search", placeholder="Company or position")

shown = table[table["Status"].isin(statuses or [])]
if search:
    needle = search.lower()
    shown = shown[shown["Company"].str.lower().str.contains(needle, regex=False)
                  | shown["Position"].str.lower().str.contains(needle, regex=False)]

answered = table["Days to answer"].notna()
with st.container(horizontal=True):
    st.metric("Applications", len(table), border=True)
    st.metric("Got an answer", f"{answered.mean():.0%}", border=True)
    st.metric("Median days to answer",
              f"{table.loc[answered, 'Days to answer'].median():.0f}" if answered.any() else "-",
              border=True)

selection = st.dataframe(
    shown,
    hide_index=True,
    column_order=[c for c in shown.columns if c != "id"],
    column_config={
        "Applied": st.column_config.DateColumn(format="DD MMM YYYY"),
        "Answered on": st.column_config.DateColumn(format="DD MMM YYYY"),
        "Days to answer": st.column_config.NumberColumn(format="%d d"),
        "Days since last news": st.column_config.NumberColumn(format="%d d"),
        "What they wrote": st.column_config.TextColumn(width="large"),
    },
    on_select="rerun",
    placeholder="–",
    selection_mode="single-row",
    key="applications_table",
    alt="Table of all job applications with dates, answers and rejection reasons",
)

st.download_button("Download as CSV", shown.drop(columns="id").to_csv(index=False).encode("utf-8"),
                   file_name="applications.csv", mime="text/csv", icon=":material/download:")

# ---------------------------------------------------------------- timeline of the selected row
rows = selection.selection.rows
if not rows:
    st.caption("Select a row to see every email of that application.")
else:
    picked = shown.iloc[rows[0]]
    st.subheader(f"{picked['Company']} · {picked['Position'] or 'position unknown'}")
    timeline = emails[emails["application_id"] == picked["id"]]
    st.dataframe(
        pd.DataFrame({
            "Date": timeline["received_at"].dt.tz_convert(None),
            "Type": timeline["category"].map(CATEGORY_LABELS),
            "Subject": timeline["subject"],
            "From": timeline["sender"],
            # Real Gmail ids open the email in Gmail; demo ids are fake, so no link there
            "Open": None if settings.demo else "https://mail.google.com/mail/u/0/#all/" + timeline["id"],
        }),
        hide_index=True,
        placeholder="–",
        column_config={
            "Date": st.column_config.DatetimeColumn(format="DD MMM YYYY, HH:mm"),
            "Open": st.column_config.LinkColumn(display_text="Open in Gmail"),
        },
        alt=f"Emails of the {picked['Company']} application",
    )
