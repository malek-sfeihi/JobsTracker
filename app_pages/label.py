"""Label emails by hand: the "gold" dataset for the machine-learning phase."""
import re
from html import unescape

import streamlit as st

from app.db.database import get_connection, save_label
from app.ml.labeling import LABELS, labeling_queue

BUTTONS = {
    "confirmation": ("Confirmation", ":material/mark_email_read:"),
    "rejection": ("Rejection", ":material/block:"),
    "assessment": ("Assessment", ":material/quiz:"),
    "interview": ("Interview", ":material/groups:"),
    "offer": ("Offer", ":material/celebration:"),
    "not_job": ("Not about an application", ":material/do_not_disturb_on:"),
}


def readable(body: str) -> str:
    text = unescape(body)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S+", "[link]", text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()[:3000]


def md_escape(text: str) -> str:
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|>~$<])", r"\\\1", text)


def label_email(email_id: str, label: str) -> None:
    conn = get_connection()
    save_label(conn, email_id, label)
    conn.close()


def undo_last() -> None:
    conn = get_connection()
    conn.execute("DELETE FROM labels WHERE email_id = "
                 "(SELECT email_id FROM labels ORDER BY labeled_at DESC LIMIT 1)")
    conn.commit()
    conn.close()


st.header("Label emails")
st.caption("You are building the ground truth that the rules and the ML model will both be graded on.")

with st.expander("Why am I doing this?", icon=":material/school:"):
    st.markdown(
        "**Supervised learning** means learning from examples that already have the right answer. "
        "A model sees thousands of *(email → category)* pairs and finds the patterns by itself. "
        "Your labels are those right answers.\n\n"
        "They also serve as the **exam**: to know if the model beats the rules, both are graded "
        "on your labels. If we graded the model on the rules' output, it could only learn to copy "
        "the rules, mistakes included.\n\n"
        "**Two tips for good labels:**\n"
        "- Judge the email on its own. The rules' guess is hidden on purpose, so it can't influence "
        "you (that influence is called *anchoring bias*).\n"
        "- \"Not about an application\" covers job alerts, newsletters and ads, even when they talk "
        "about jobs. Only emails about an application *you* sent get a category."
    )

conn = get_connection()
queue = labeling_queue(conn)
labeled = {row["email_id"] for row in conn.execute("SELECT email_id FROM labels")}
skipped = st.session_state.setdefault("skipped", set())
remaining = [email_id for email_id in queue if email_id not in labeled and email_id not in skipped]
done = sum(email_id in labeled for email_id in queue)

st.progress(done / len(queue), text=f"{done} of {len(queue)} labeled")

if not remaining:
    st.success("All done! Your gold dataset is ready for training.", icon=":material/check_circle:")
    conn.close()
    st.stop()

email_id = remaining[0]
email = conn.execute(
    "SELECT sender, subject, received_at, body FROM emails WHERE id = ?", (email_id,)
).fetchone()
conn.close()

with st.container(border=True):
    st.markdown(f"**{md_escape(email['subject'] or '(no subject)')}**")
    st.caption(f"From {md_escape(email['sender'])} · {email['received_at'][:10]}")
    with st.container(height=320, border=False):
        st.text(readable(email["body"]))

with st.container(horizontal=True):
    for label in LABELS:
        name, icon = BUTTONS[label]
        st.button(name, icon=icon, key=f"label_{label}", on_click=label_email, args=(email_id, label))

with st.container(horizontal=True):
    st.button("Skip for now", icon=":material/skip_next:", type="tertiary",
              on_click=lambda: skipped.add(email_id))
    st.button("Undo last label", icon=":material/undo:", type="tertiary", on_click=undo_last,
              disabled=not labeled)
