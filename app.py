"""app.py -- Streamlit UI for the personal interview-prep study tracker.

Run locally:   streamlit run app.py
Deploy:        push to GitHub, then Streamlit Community Cloud (free).

You log what you studied each day (topic + a 1-5 confidence). The app looks
back over your history and tells you what to focus on tomorrow, this week, and
this month -- prioritising weak and stale topics and flagging syllabus gaps.
"""

import json
import os
from datetime import date

import streamlit as st

import engine

st.set_page_config(page_title="Interview Prep Tracker", page_icon="📚", layout="wide")


def _load_secrets_into_env():
    """Copy Streamlit secrets into env so engine.py (which reads os.environ)
    can find Turso / Gemini credentials when deployed. No-op if unset."""
    for k in ("TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN",
              "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        try:
            if k in st.secrets and not os.environ.get(k):
                os.environ[k] = str(st.secrets[k])
        except Exception:
            pass


_load_secrets_into_env()


@st.cache_resource
def _bootstrap():
    """Create the table / run migration once per app instance."""
    engine.init_db()
    return True


_bootstrap()

syllabus = engine.load_syllabus()


def refresh_log():
    st.session_state.log = engine.load_log()


if "log" not in st.session_state:
    refresh_log()

log = st.session_state.log
today = date.today()


# --------------------------------------------------------------------------- #
# Sidebar: stats + backup
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("📊 At a glance")
    overview = engine.monthly_overview(syllabus, log, today)
    st.metric("Syllabus covered", f"{overview['coverage_pct']}%",
              help=f"{overview['studied']} of {overview['total']} topics touched")
    st.metric("Current streak", f"{engine.current_streak(log, today)} days")
    st.metric("Entries logged", len(log))

    st.divider()
    storage = ("☁️ Turso — persists across redeploys"
               if os.environ.get("TURSO_DATABASE_URL")
               and os.environ.get("TURSO_AUTH_TOKEN")
               else "💾 Local file (data/study.db)")
    st.caption(f"Storage: {storage}")
    st.caption("Backup / restore your log")
    st.download_button(
        "⬇️ Download log.json",
        data=json.dumps(log, indent=2),
        file_name="log.json",
        mime="application/json",
        use_container_width=True,
    )
    uploaded = st.file_uploader("⬆️ Restore log.json", type="json")
    if uploaded is not None:
        try:
            restored = json.load(uploaded)
            engine.save_log(restored)
            refresh_log()
            st.success("Log restored.")
            st.rerun()
        except Exception as e:
            st.error(f"Couldn't read that file: {e}")


st.title("📚 Interview Prep Tracker")
st.caption("Log your daily learning. Get a personalised plan for tomorrow, "
           "this week, and this month.")

tab_log, tab_plan, tab_overview = st.tabs(
    ["✍️ Log today", "🗺️ My plan", "📈 Overview"]
)


# --------------------------------------------------------------------------- #
# Tab 1: Log today's study
# --------------------------------------------------------------------------- #
with tab_log:
    st.subheader("What did you study or revise?")

    col1, col2 = st.columns(2)
    with col1:
        subject = st.selectbox("Subject", list(syllabus.keys()))
    with col2:
        subtopic = st.selectbox("Topic", syllabus[subject])

    confidence = st.slider(
        "How confident do you feel now?", 1, 5, 3,
        help="1 = just started · 5 = interview-ready",
    )
    st.caption(f"→ {engine.CONFIDENCE_LABELS[confidence]}")

    notes = st.text_input("Notes (optional)",
                          placeholder="e.g. revisit deadlock recovery, felt slow on DP")

    log_date = st.date_input("Date", value=today)

    if st.button("💾 Save entry", type="primary"):
        engine.add_entry(subject, subtopic, confidence, notes, when=log_date)
        refresh_log()
        st.success(f"Logged **{subject} → {subtopic}** "
                   f"({engine.CONFIDENCE_LABELS[confidence]}).")
        st.rerun()

    # Recent activity
    if log:
        st.divider()
        st.subheader("Recent entries")
        recent = sorted(log, key=lambda e: (e["date"], e.get("id", 0)),
                        reverse=True)[:8]
        for e in recent:
            badge = engine.CONFIDENCE_LABELS[e["confidence"]]
            col_txt, col_btn = st.columns([12, 1])
            with col_txt:
                line = (f"**{e['date']}** — {e['subject']} → {e['subtopic']}"
                        f"  ·  _{badge}_")
                if e.get("notes"):
                    line += f"  \n  📝 {e['notes']}"
                st.markdown(line)
            with col_btn:
                if e.get("id") is not None and st.button(
                        "🗑️", key=f"del_{e['id']}", help="Delete this entry"):
                    engine.delete_entry(e["id"])
                    refresh_log()
                    st.rerun()


# --------------------------------------------------------------------------- #
# Tab 2: The plan
# --------------------------------------------------------------------------- #
def render_item(item):
    """One line for a plan item, with a reason tag."""
    if item.get("status") == "new":
        tag = "🆕 new topic"
    else:
        conf = engine.CONFIDENCE_LABELS.get(item.get("confidence", 3), "")
        if item.get("overdue", 0) >= 0:
            tag = f"🔁 due for revision · last {conf.lower()} · {item['days_since']}d ago"
        else:
            tag = f"🔁 revision soon · last {conf.lower()}"
    st.markdown(f"- **{item['subject']} → {item['subtopic']}**  \n  <small>{tag}</small>",
                unsafe_allow_html=True)


with tab_plan:
    if not log:
        st.info("Log a few study sessions first, then your plan will appear here.")
    else:
        daily = engine.daily_plan(syllabus, log, today)
        weekly = engine.weekly_plan(syllabus, log, today)
        monthly = engine.monthly_overview(syllabus, log, today)

        use_ai = st.toggle(
            "✨ Write it up with AI (Gemini)",
            value=False,
            help="Optional. Needs GEMINI_API_KEY set in your environment / Streamlit secrets.",
        )

        if use_ai:
            with st.spinner("Asking Gemini to summarise your plan..."):
                text = engine.narrative_plan(daily, weekly, monthly)
            if text:
                st.markdown(text)
            else:
                st.warning("AI narrative unavailable (no API key or SDK). "
                           "Showing the rule-based plan below.")
                use_ai = False

        if not use_ai:
            st.subheader(f"🌅 Tomorrow — {daily['for_date']}")
            if daily["revise"]:
                st.markdown("**Revise:**")
                for it in daily["revise"]:
                    render_item(it)
            if daily["learn"]:
                st.markdown("**Learn something new:**")
                for it in daily["learn"]:
                    render_item(it)
            if not daily["revise"] and not daily["learn"]:
                st.success("All caught up — nothing urgent. Pick anything you enjoy!")

            st.divider()
            st.subheader("🗓️ This week")
            for day in weekly:
                with st.expander(f"{day['weekday']} · {day['date']}"):
                    if day["items"]:
                        for it in day["items"]:
                            render_item(it)
                    else:
                        st.caption("Free day / buffer.")

            st.divider()
            st.subheader("📆 This month — focus areas")
            if monthly["stale"]:
                st.markdown("**Going stale (revise soon):**")
                for it in monthly["stale"][:8]:
                    st.markdown(
                        f"- **{it['subject']} → {it['subtopic']}** · "
                        f"{it['days_since']}d since last review"
                    )
            if monthly["untouched"]:
                st.markdown(f"**Not started yet ({len(monthly['untouched'])} topics):**")
                preview = monthly["untouched"][:10]
                st.markdown(
                    ", ".join(f"{it['subject']}: {it['subtopic']}" for it in preview)
                    + (" …" if len(monthly["untouched"]) > 10 else "")
                )
            if not monthly["stale"] and not monthly["untouched"]:
                st.success("Full syllabus covered and nothing stale. Strong position!")


# --------------------------------------------------------------------------- #
# Tab 3: Overview
# --------------------------------------------------------------------------- #
with tab_overview:
    overview = engine.monthly_overview(syllabus, log, today)

    st.subheader("Coverage by subject")
    for subject, stat in overview["per_subject"].items():
        done, total = stat["done"], stat["total"]
        st.markdown(f"**{subject}** — {done}/{total}")
        st.progress(done / total if total else 0)

    st.divider()
    st.subheader("Confidence spread")
    dist = overview["confidence_distribution"]
    cols = st.columns(5)
    for i, c in enumerate(cols, start=1):
        c.metric(engine.CONFIDENCE_LABELS[i], dist[i])

    if overview["stale"]:
        st.divider()
        st.subheader("⚠️ Stale topics (14+ days)")
        for it in overview["stale"]:
            st.markdown(
                f"- {it['subject']} → {it['subtopic']} "
                f"({it['days_since']}d, last {engine.CONFIDENCE_LABELS[it['confidence']].lower()})"
            )
