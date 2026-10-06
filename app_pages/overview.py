"""Overview page: the morning view of the job search."""
from datetime import datetime, timezone
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

from app.core.config import settings
from app.db.database import get_connection, save_override
from app.filters.reasons import REASON_LABELS
from app.services.applications import build_applications

# ---------------------------------------------------------------- design tokens
# Only open applications get a color; closed ones (rejected/expired) recede into gray.
# Validated as an ordered palette (coral, blue, green, lavender) on a white surface:
# blue and lavender are never adjacent, and every color always comes with an icon + label.
INK = "#1F2433"
INK_SECONDARY = "#5B6070"
INK_MUTED = "#8A8F9C"
ACCENT = "#5E4E96"        # plum-lilac: single-series charts (validated vs ghosted lavender)
GRID = "#ECE9E3"
CLOSED_GRAY = "#C9C5BD"

# Display order = pipeline order (also the order of the stacked bar segments)
GROUPS = {
    "action_needed": {"label": "Your turn", "icon": "✋", "color": "#D9694F"},
    "in_progress": {"label": "Waiting for them", "icon": "⏳", "color": "#3D7DD8"},
    "offer": {"label": "Offer", "icon": "🎉", "color": "#2A9D6E"},
    "ghosted": {"label": "Ghosted", "icon": "👻", "color": "#8B7FD1"},
    "closed": {"label": "Closed", "icon": "·", "color": CLOSED_GRAY},
}
STATUS_TO_GROUP = {
    "action_needed": "action_needed", "in_progress": "in_progress", "offer": "offer",
    "ghosted": "ghosted", "rejected": "closed", "expired": "closed",
}
STATUS_LABELS = {
    "action_needed": "✋ Your turn", "in_progress": "⏳ Waiting for them", "offer": "🎉 Offer",
    "ghosted": "👻 Ghosted", "rejected": "✕ Rejected", "expired": "⌛ Expired",
}
LABEL_TO_STATUS = {label: status for status, label in STATUS_LABELS.items()}

QUOTES = [
    "Every application is a door you knocked on. Some open later than you think.",
    "Rejections measure fit, not worth.",
    "Consistency beats intensity. A few good applications a day add up.",
    "You only need one yes.",
    "The right team is also looking for you.",
    "Progress, not perfection.",
    "Each no is one step closer to the right yes.",
]


st.markdown(
    f"""
    <style>
      .block-container {{ padding-top: 2.2rem; max-width: 1200px; }}
      h1, h2, h3 {{ color: {INK}; letter-spacing: -0.01em; }}
      .hero {{
        background: linear-gradient(120deg, #EDE5F7 0%, #F5EFF8 45%, #FAF6F0 100%);
        border-radius: 20px; padding: 26px 30px 22px; border: 1px solid #E8E0F2;
      }}
      .hello {{ font-size: 2.1rem; font-weight: 650; color: {INK}; margin: 0; }}
      .date {{ color: {INK_MUTED}; font-size: 0.95rem; margin-bottom: 0.4rem; }}
      .mood {{ color: {INK_SECONDARY}; font-size: 1.08rem; margin: 0.2rem 0 0.2rem; }}
      .quote {{ color: {INK_MUTED}; font-style: italic; font-size: 0.95rem; }}
      .card {{
        background: #FFFFFF; border: 1px solid rgba(31,36,51,0.07); border-radius: 16px;
        border-top: 3px solid #D8CCEC;  /* thin lilac line */
        padding: 18px 20px; height: 100%; box-shadow: 0 1px 3px rgba(94,78,150,0.06);
      }}
      .kpi-label {{ color: {INK_SECONDARY}; font-size: 0.85rem; }}
      .kpi-value {{ color: {INK}; font-size: 2.1rem; font-weight: 650; line-height: 1.25; }}
      .kpi-sub {{ color: {INK_MUTED}; font-size: 0.8rem; }}
      .section {{ color: {INK}; font-size: 1.15rem; font-weight: 600; margin: 1.6rem 0 0.6rem; }}
      .item {{
        background: #FFFFFF; border-radius: 12px; padding: 10px 14px; margin-bottom: 8px;
        border: 1px solid rgba(31,36,51,0.07); border-left: 4px solid var(--c);
      }}
      .item-title {{ color: {INK}; font-weight: 600; }}
      .item-sub {{ color: {INK_MUTED}; font-size: 0.85rem; }}
      .empty {{ color: {INK_MUTED}; font-size: 0.95rem; padding: 6px 2px; }}
      .why {{ color: {INK_SECONDARY}; font-style: italic; font-size: 0.9rem; margin-top: 4px; }}
      .chips {{ display: flex; flex-wrap: wrap; gap: 8px 18px; margin-top: 4px; }}
      .chip {{ color: {INK_SECONDARY}; font-size: 0.9rem; }}
      .dot {{
        display: inline-block; width: 10px; height: 10px; border-radius: 3px;
        background: var(--c); margin-right: 6px; vertical-align: baseline;
      }}
      .chip b {{ color: {INK}; }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- data
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    conn = get_connection()
    apps = pd.read_sql("SELECT * FROM applications", conn)
    emails = pd.read_sql(
        "SELECT application_id, received_at, category FROM emails WHERE application_id IS NOT NULL",
        conn,
    )
    conn.close()
    for column in ("first_activity", "last_activity"):
        apps[column] = pd.to_datetime(apps[column], utc=True, format="ISO8601")
    emails["received_at"] = pd.to_datetime(emails["received_at"], utc=True, format="ISO8601")
    return apps, emails


def nice_name(name: str) -> str:
    # Extracted names are lowercase ("blablacar"); corrected ones keep your capitalization
    return name.title() if name == name.lower() and "." not in name else name


def days_ago(when: pd.Timestamp, now: datetime) -> str:
    days = (now - when).days
    return "today" if days == 0 else "yesterday" if days == 1 else f"{days} days ago"


def card(label: str, value: str, sub: str) -> str:
    return (f'<div class="card"><div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}</div><div class="kpi-sub">{sub}</div></div>')


def item(app: pd.Series, color: str, sub: str, quote: str = "") -> str:
    # Careful: SQL NULL becomes NaN in pandas, and NaN counts as True in an `if`
    position = f" · {escape(app['position'])}" if pd.notna(app["position"]) else ""
    why = f'<div class="why">“{quote}”</div>' if quote else ""
    return (f'<div class="item" style="--c:{color}"><div class="item-title">'
            f'{escape(nice_name(app["company"]))}<span class="item-sub">{position}</span></div>'
            f'<div class="item-sub">{sub}</div>{why}</div>')


def style_chart(chart: alt.Chart) -> alt.Chart:
    return (chart.configure_view(stroke=None)
            .configure_axis(gridColor=GRID, domainColor="#D6D2CA", tickColor="#D6D2CA",
                            labelColor=INK_MUTED, titleColor=INK_MUTED, labelFontSize=11)
            .configure(background="#FFFFFF", padding={"left": 14, "right": 14, "top": 14, "bottom": 8}))


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("### 🌿 JobsTracker")
    if settings.demo:
        if not settings.db_path.exists():
            from app.demo import seed_demo
            seed_demo()
        st.info("Demo mode: fictional companies and emails.", icon=":material/science:")
    elif st.button("Sync with Gmail", icon="🔄", width="stretch"):
        from app.services.sync import sync
        with st.spinner("Reading new emails..."):
            new_count = sync()
            build_applications()
        st.toast(f"{new_count} new email(s) synced")
    # Last sync (the 7:00 scheduled one, or a manual click): reassure, or warn if it failed
    conn = get_connection()
    last_run = conn.execute("SELECT * FROM sync_runs ORDER BY ran_at DESC LIMIT 1").fetchone()
    conn.close()
    if last_run:
        when = datetime.fromisoformat(last_run["ran_at"]).astimezone()  # UTC -> your local time
        label = f"{when:%H:%M}" if when.date() == datetime.now().date() else f"{when:%d %b, %H:%M}"
        if last_run["ok"]:
            st.caption(f":material/check_circle: Synced at {label} · {last_run['new_emails']} new email(s)")
        else:
            st.warning(f"Last sync failed ({label}): {last_run['message']}", icon=":material/error:")
    weekly_goal = st.number_input("Weekly goal (applications)", min_value=1, max_value=50, value=5)
    st.caption(f"Ghosted = no news for {settings.ghost_days}+ days.")

apps, emails = load_data()
now = datetime.now(timezone.utc)

if apps.empty:
    st.info("No applications yet. Click **Sync with Gmail** in the sidebar to get started.")
    st.stop()

apps["group"] = apps["status"].map(STATUS_TO_GROUP)
jobs = apps[apps["kind"] == "job"]
counts = apps["group"].value_counts()

# ---------------------------------------------------------------- greeting
hour = datetime.now().hour
greeting, sky = (("Good morning", "☀️") if hour < 12
                 else ("Good afternoon", "🌤️") if hour < 18 else ("Good evening", "🌙"))
your_turn = int(counts.get("action_needed", 0))
waiting = int(counts.get("in_progress", 0))
if your_turn:
    mood = f"{your_turn} thing{'s' if your_turn > 1 else ''} need{'' if your_turn > 1 else 's'} you today. Start there, the rest can wait."
elif waiting:
    mood = f"Nothing urgent. {waiting} companies are reading your CV right now. A calm moment to send a new one."
else:
    mood = "A clean slate. Today is a good day to send a few applications."

st.markdown(
    f'<div class="hero"><div class="hello">{greeting}, {escape(settings.user_name)} {sky}</div>'
    f'<div class="date">{datetime.now():%A %d %B %Y}</div>'
    f'<div class="mood">{mood}</div>'
    f'<div class="quote">“{QUOTES[now.timetuple().tm_yday % len(QUOTES)]}”</div></div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- KPI row
answered_ids = set(emails.loc[emails["category"] != "confirmation", "application_id"])
response_rate = jobs["id"].isin(answered_ids).mean() if len(jobs) else 0
week_start = pd.Timestamp(now).normalize() - pd.Timedelta(days=now.weekday())
this_week = int((jobs["first_activity"] >= week_start).sum())

st.write("")
k1, k2, k3, k4 = st.columns(4)
k1.markdown(card("Applications sent", f"{len(jobs)}",
                 f"since {jobs['first_activity'].min():%d %b}"), unsafe_allow_html=True)
k2.markdown(card("Waiting for an answer", f"{waiting}",
                 f"less than {settings.ghost_days} days old"), unsafe_allow_html=True)
k3.markdown(card("Response rate", f"{response_rate:.0%}",
                 "companies that replied, yes or no"), unsafe_allow_html=True)
with k4:
    st.markdown(card("This week", f"{this_week} / {weekly_goal}",
                     "goal reached 🌿" if this_week >= weekly_goal else f"{weekly_goal - this_week} to go, you've got this"),
                unsafe_allow_html=True)
    st.progress(min(this_week / weekly_goal, 1.0))

# ---------------------------------------------------------------- today
left, right = st.columns(2, gap="large")
with left:
    st.markdown('<div class="section">✋ Your turn</div>', unsafe_allow_html=True)
    todo = apps[apps["status"] == "action_needed"].sort_values("last_activity")
    if todo.empty:
        st.markdown('<div class="empty">Nothing waiting on you. ✓</div>', unsafe_allow_html=True)
    for _, app in todo.iterrows():
        st.markdown(item(app, GROUPS["action_needed"]["color"],
                         f"invitation received {days_ago(app['last_activity'], now)}"),
                    unsafe_allow_html=True)

with right:
    st.markdown('<div class="section">💌 Worth a follow-up</div>', unsafe_allow_html=True)
    # Recently ghosted = still warm: a short polite email can revive these
    recent_ghosts = apps[(apps["status"] == "ghosted")
                         & ((now - apps["last_activity"]).dt.days <= 2 * settings.ghost_days)]
    recent_ghosts = recent_ghosts.sort_values("last_activity", ascending=False).head(5)
    if recent_ghosts.empty:
        st.markdown('<div class="empty">No recent silence to chase.</div>', unsafe_allow_html=True)
    for _, app in recent_ghosts.iterrows():
        st.markdown(item(app, GROUPS["ghosted"]["color"],
                         f"last news {days_ago(app['last_activity'], now)}"),
                    unsafe_allow_html=True)

# ---------------------------------------------------------------- pipeline
st.markdown('<div class="section">Where everything stands</div>', unsafe_allow_html=True)
pipeline = pd.DataFrame([
    {"group": key, "label": f"{g['icon']} {g['label']}", "count": int(counts.get(key, 0)), "order": i}
    for i, (key, g) in enumerate(GROUPS.items())
])
pipeline = pipeline[pipeline["count"] > 0]
bar = alt.Chart(pipeline).mark_bar(
    height=30, cornerRadius=4, stroke="#FFFFFF", strokeWidth=2
).encode(
    x=alt.X("count:Q", stack="normalize", axis=None),
    color=alt.Color("group:N", legend=None, scale=alt.Scale(
        domain=list(GROUPS), range=[g["color"] for g in GROUPS.values()])),
    order=alt.Order("order:Q"),
    tooltip=[alt.Tooltip("label:N", title="Status"), alt.Tooltip("count:Q", title="Applications")],
).properties(height=30)
st.altair_chart(style_chart(bar), width="stretch")
st.markdown(
    '<div class="chips">' + "".join(
        f'<span class="chip"><span class="dot" style="--c:{GROUPS[row.group]["color"]}"></span>'
        f'{row.label} <b>{row.count}</b></span>'
        for row in pipeline.itertuples()
    ) + "</div>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- rejection reasons
rejected = apps[apps["status"] == "rejected"].sort_values("last_activity", ascending=False)
if not rejected.empty:
    st.markdown('<div class="section">Why companies said no</div>', unsafe_allow_html=True)
    reasons = (rejected["rejection_reason"].fillna("no_reason").map(REASON_LABELS)
               .value_counts().rename_axis("reason").reset_index(name="count"))
    base = alt.Chart(reasons).encode(
        y=alt.Y("reason:N", sort="-x", title=None, axis=alt.Axis(labelLimit=260, labelColor=INK_SECONDARY)),
        x=alt.X("count:Q", title=None, axis=None),
        tooltip=[alt.Tooltip("reason:N", title="Reason"), alt.Tooltip("count:Q", title="Rejections")],
    )
    reason_chart = (
        base.mark_bar(color=ACCENT, cornerRadiusTopRight=4, cornerRadiusBottomRight=4, size=16)
        + base.mark_text(align="left", dx=6, color=INK_SECONDARY, fontSize=12).encode(text="count:Q")
    ).properties(height=34 * len(reasons))
    st.altair_chart(style_chart(reason_chart), width="stretch")

    # The honest, reassuring read of the data: most rejections are not about your skills
    mismatch = int((rejected["rejection_reason"] == "profile_mismatch").sum())
    rules = rejected["rejection_reason"].isin(["eligibility", "location", "format", "position_closed"])
    st.caption(
        f"Only {mismatch} of {len(rejected)} rejections say your profile didn't match. "
        f"The rest came down to competition, timing or rules you couldn't control."
        + (f" {int(rules.sum())} were about eligibility, location, format or a closed position: "
           "checking those requirements before applying saves effort." if rules.any() else "")
    )

    with st.expander(f"Read what each company said ({len(rejected)})"):
        for _, app in rejected.iterrows():
            reason = REASON_LABELS[app["rejection_reason"] or "no_reason"]
            quote = escape(app["rejection_quote"]) if pd.notna(app["rejection_quote"]) else ""
            st.markdown(item(app, CLOSED_GRAY, f"<b>{reason}</b> · {days_ago(app['last_activity'], now)}",
                             quote=quote), unsafe_allow_html=True)

# ---------------------------------------------------------------- charts
c1, c2 = st.columns(2, gap="large")
with c1:
    st.markdown('<div class="section">Your momentum</div>', unsafe_allow_html=True)
    weeks = jobs["first_activity"].dt.tz_convert(None).dt.to_period("W-SUN").dt.start_time
    weekly = weeks.value_counts().rename_axis("week").reset_index(name="count")
    all_weeks = pd.date_range(weekly["week"].min(), week_start.tz_convert(None), freq="W-MON")
    weekly = (weekly.set_index("week").reindex(all_weeks, fill_value=0)
              .rename_axis("week").reset_index())
    weekly["label"] = weekly["week"].dt.strftime("%d %b")
    momentum = alt.Chart(weekly).mark_bar(
        color=ACCENT, cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=22
    ).encode(
        x=alt.X("label:O", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("count:Q", title=None, axis=alt.Axis(tickMinStep=1)),
        tooltip=[alt.Tooltip("label:N", title="Week of"), alt.Tooltip("count:Q", title="Applications")],
    ).properties(height=240)
    st.altair_chart(style_chart(momentum), width="stretch")
    st.caption("Applications sent per week.")

with c2:
    st.markdown('<div class="section">How fast companies answer</div>', unsafe_allow_html=True)
    first = emails.groupby("application_id")["received_at"].min()
    first_answer = (emails[emails["category"] != "confirmation"]
                    .groupby("application_id")["received_at"].min())
    delay = (first_answer - first.reindex(first_answer.index)).dt.days
    buckets = pd.cut(delay, bins=[-1, 1, 3, 7, 14, 10_000],
                     labels=["0–1 day", "2–3 days", "4–7 days", "8–14 days", "15+ days"])
    speed = buckets.value_counts(sort=False).rename_axis("delay").reset_index(name="count")
    speed_chart = alt.Chart(speed).mark_bar(
        color=ACCENT, cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=34
    ).encode(
        x=alt.X("delay:O", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("count:Q", title=None, axis=alt.Axis(tickMinStep=1)),
        tooltip=[alt.Tooltip("delay:N", title="Answer after"), alt.Tooltip("count:Q", title="Replies")],
    ).properties(height=240)
    st.altair_chart(style_chart(speed_chart), width="stretch")
    if len(delay):
        fast = (delay <= 3).mean()
        st.caption(f"{fast:.0%} of replies came within 3 days, often a sign of automated CV "
                   "screening. Tailoring keywords to each offer can help.")

# ---------------------------------------------------------------- all applications
st.markdown('<div class="section">All applications</div>', unsafe_allow_html=True)
f1, f2 = st.columns([2, 1])
chosen = f1.multiselect("Status", list(STATUS_LABELS.values()),
                        default=[STATUS_LABELS[s] for s in ("action_needed", "in_progress", "ghosted", "offer")])
search = f2.text_input("Search company or position")

table = apps[apps["status"].map(STATUS_LABELS).isin(chosen)].copy()
if search:
    needle = search.lower()
    table = table[table["company"].str.lower().str.contains(needle, regex=False)
                  | table["position"].fillna("").str.lower().str.contains(needle, regex=False)]
table = table.sort_values("last_activity", ascending=False)
table["Status"] = table["status"].map(STATUS_LABELS)
table["Company"] = table["company"].map(nice_name)
table["Position"] = table["position"].fillna("")
table["Applied"] = table["first_activity"].dt.tz_convert(None)
table["Last news"] = (now - table["last_activity"]).dt.days.astype(str) + " d ago"
table["Type"] = table["kind"]
table["Why"] = table["rejection_reason"].map(REASON_LABELS).fillna("")
columns = ["Status", "Company", "Position", "Why", "Applied", "Last news", "Type"]

edited = st.data_editor(
    table[columns + ["anchor_email_id"]].set_index("anchor_email_id"),
    column_order=columns,
    hide_index=True,
    width="stretch",
    disabled=["Why", "Applied", "Last news", "Type"],
    column_config={
        "Status": st.column_config.SelectboxColumn(options=list(STATUS_LABELS.values()), required=True),
        "Applied": st.column_config.DateColumn(format="DD MMM YYYY"),
    },
    key="editor",
)

if st.button("Save my corrections", icon="💾"):
    original = table.set_index("anchor_email_id")
    conn = get_connection()
    changed = 0
    for anchor, row in edited.iterrows():
        before = original.loc[anchor]
        if (row["Status"], row["Company"], row["Position"]) != (before["Status"], before["Company"], before["Position"]):
            save_override(
                conn, anchor,
                company=row["Company"] if row["Company"] != before["Company"] else None,
                position=(row["Position"] or None) if row["Position"] != before["Position"] else None,
                status=LABEL_TO_STATUS[row["Status"]] if row["Status"] != before["Status"] else None,
            )
            changed += 1
    conn.commit()
    conn.close()
    build_applications()
    st.toast(f"{changed} correction(s) saved")
    st.rerun()
