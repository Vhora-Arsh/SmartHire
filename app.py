"""SmartHire - HR dashboard (Streamlit).
Runs on demo data by default. Add secrets (see README.md) to use Airtable + n8n.
"""
import random
from datetime import date, timedelta

import altair as alt
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="SmartHire", page_icon="📋", layout="wide")

INK, ACCENT, GREEN, AMBER, RED, LINE = "#1B2133", "#4F46E5", "#16A34A", "#D97706", "#DC2626", "#E6E9F2"
PARAMS = ["Technical Skills", "Experience Relevance", "Education", "Tools & Technologies", "Soft Skills"]

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@600;700;800&family=Inter:wght@400;500;600&display=swap');
html, body, [class*="css"], .stMarkdown, button, input {{ font-family: 'Inter', sans-serif; color: {INK}; }}
h1, h2, h3, .sh-title {{ font-family: 'Manrope', sans-serif !important; letter-spacing: -0.02em; color: {INK}; }}
header[data-testid="stHeader"], footer, #MainMenu {{ display: none; }}
.block-container {{ padding: 2rem 2.5rem 3rem; max-width: 1240px; }}
[data-testid="stSidebar"] {{ background: #fff; border-right: 1px solid {LINE}; }}
.brand {{ font: 800 1.5rem 'Manrope'; padding: .4rem 0 1.2rem; }} .brand b {{ color: {ACCENT}; }}
.page-title {{ font: 800 1.9rem 'Manrope'; margin: 0; }} .page-sub {{ color: #667085; margin: .2rem 0 1.6rem; }}
.card {{ background: #fff; border: 1px solid {LINE}; border-radius: 14px; padding: 1.1rem 1.3rem; }}
.kpi .v {{ font: 800 2rem 'Manrope'; line-height: 1.1; }} .kpi .l {{ color: #667085; font-size: .85rem; margin-top: .25rem; }}
.pill {{ display: inline-block; padding: .15rem .65rem; border-radius: 999px; font-size: .78rem; font-weight: 600; }}
.pill.open {{ background: #E8F6EE; color: {GREEN}; }} .pill.closed {{ background: #FDECEC; color: {RED}; }}
.chip {{ display: inline-block; padding: .2rem .7rem; margin: 0 .35rem .35rem 0; border-radius: 8px; font-size: .82rem; }}
.chip.miss {{ background: #FDECEC; color: {RED}; }} .chip.part {{ background: #FEF3E2; color: {AMBER}; }}
.ring {{ width: 140px; height: 140px; border-radius: 50%; display: grid; place-items: center;
        background: conic-gradient(var(--c) calc(var(--p) * 1%), {LINE} 0); }}
.ring span {{ width: 108px; height: 108px; border-radius: 50%; background: #fff; display: grid; place-items: center;
        font: 800 2.2rem 'Manrope'; }} .ring small {{ font: 500 .75rem 'Inter'; color: #667085; display: block; text-align: center; margin-top: -1.3rem; }}
.bar {{ height: 8px; border-radius: 6px; background: {LINE}; overflow: hidden; }} .bar i {{ display: block; height: 100%; background: {ACCENT}; }}
.prow {{ display: flex; justify-content: space-between; font-size: .9rem; margin: .8rem 0 .3rem; }}
.report {{ white-space: pre-wrap; line-height: 1.6; font-size: .93rem; }}
div.stButton > button {{ border-radius: 10px; font-weight: 600; border: 1px solid {LINE}; }}
div.stButton > button[kind="primary"] {{ background: {ACCENT}; border-color: {ACCENT}; }}
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- data
def tone(score):
    return (GREEN, "Strong match") if score >= 75 else (AMBER, "Possible match") if score >= 55 else (RED, "Weak match")


def demo_data():
    rnd = random.Random(7)
    positions = [
        dict(title="Python Developer", status="Open", vacancies=2, priority="High"),
        dict(title="Data Analyst", status="Open", vacancies=1, priority="Medium"),
        dict(title="ML Engineer", status="Open", vacancies=3, priority="High"),
        dict(title="UI/UX Designer", status="Open", vacancies=1, priority="Low"),
        dict(title="DevOps Engineer", status="Closed", vacancies=0, priority="Medium"),
    ]
    names = ["Aarav Shah", "Diya Patel", "Rohan Mehta", "Isha Desai", "Kabir Joshi", "Meera Nair", "Vivaan Rao",
             "Ananya Iyer", "Arjun Kapoor", "Saanvi Gupta", "Neel Trivedi", "Riya Chauhan"]
    skills_by_pos = {"Python Developer": ["Python", "Django/Flask", "REST APIs", "SQL", "Git"],
                     "Data Analyst": ["SQL", "Excel", "Power BI", "Statistics", "Python"],
                     "ML Engineer": ["Python", "PyTorch", "Model deployment", "MLOps", "Statistics"],
                     "UI/UX Designer": ["Figma", "User research", "Prototyping", "Design systems", "HTML/CSS"]}
    rows = []
    for i, n in enumerate(names):
        pos = rnd.choice(list(skills_by_pos))
        params = {p: rnd.randint(35, 96) for p in PARAMS}
        score = round(sum(params.values()) / len(PARAMS))
        skills = {s: rnd.randint(3, 10) for s in skills_by_pos[pos]}
        missing = [s for s, v in skills.items() if v <= 4]
        partial = [s for s, v in skills.items() if 5 <= v <= 6]
        rows.append(dict(name=n, email=f"{n.split()[0].lower()}@example.com", position=pos, score=score,
                         date=date.today() - timedelta(days=rnd.randint(0, 20)), params=params, skills=skills,
                         missing=missing, partial=partial, status="New",
                         report=f"{n} applied for {pos} and scored {score}/100.\n\nStrengths: relevant experience and tools match the job description.\nGaps: {', '.join(missing) or 'none identified'}.\n\n(Demo text - the real report from GPT-4o appears here.)"))
    return positions, rows


@st.cache_data(ttl=60, show_spinner="Loading from Airtable...")
def load_airtable():
    from pyairtable import Api
    api, base = Api(st.secrets["AIRTABLE_TOKEN"]), st.secrets["AIRTABLE_BASE_ID"]
    pos = [dict(title=r["fields"].get("Job Title", ""), status=r["fields"].get("Status", "Open"),
                vacancies=r["fields"].get("Vacancy Count", 0), priority=r["fields"].get("Priority", "-"), id=r["id"])
           for r in api.table(base, "Job Positions").all()]
    res = []
    for r in api.table(base, "Screening Results").all():
        f = r["fields"]
        p = f.get("Position", "")
        res.append(dict(name=f.get("Candidate", "Unknown"), email=f.get("Email", ""), position=p[0] if isinstance(p, list) else p,
                        score=int(f.get("Overall Score", 0)), date=pd.to_datetime(f.get("Received On", date.today())).date(),
                        params={k: f[k] for k in PARAMS if k in f} or None, skills=None, missing=[], partial=[],
                        status=f.get("Decision", "New"), report=f.get("Screening Report", "No report stored."), id=r["id"]))
    return pos, res


def webhook(action, payload):
    try:
        url = st.secrets.get("N8N_WEBHOOK_URL", "")
    except Exception:
        url = ""
    if not url:
        st.toast("Demo mode: no n8n webhook configured, change kept on screen only.", icon="ℹ️")
        return
    try:
        requests.post(url, json={"action": action, **payload}, timeout=10).raise_for_status()
        st.toast("Sent to n8n.", icon="✅")
    except Exception as e:
        st.toast(f"n8n request failed: {e}", icon="⚠️")


if "data" not in st.session_state:
    try:
        st.session_state.data = load_airtable() if "AIRTABLE_TOKEN" in st.secrets else demo_data()
        st.session_state.live = "AIRTABLE_TOKEN" in st.secrets
    except Exception:
        st.session_state.data, st.session_state.live = demo_data(), False
positions, cands = st.session_state.data
df = pd.DataFrame(cands)


def header(title, sub):
    st.markdown(f"<p class='page-title'>{title}</p><p class='page-sub'>{sub}</p>", unsafe_allow_html=True)


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("<div class='brand'>Smart<b>Hire</b></div>", unsafe_allow_html=True)
    page = st.radio("Navigate", ["Dashboard", "Candidates", "Positions"], label_visibility="collapsed")
    st.caption("Live data from Airtable" if st.session_state.live else "Showing demo data")


# ---------------------------------------------------------------- pages
if page == "Dashboard":
    header("Dashboard", "Every application screened by SmartHire, at a glance.")
    open_n = sum(p["status"] == "Open" for p in positions)
    kpis = [(len(df), "Applications screened"), (open_n, "Open positions"),
            (round(df.score.mean()) if len(df) else 0, "Average score"), (int((df.score >= 75).sum()), "Strong matches (75+)")]
    for col, (v, l) in zip(st.columns(4), kpis):
        col.markdown(f"<div class='card kpi'><div class='v'>{v}</div><div class='l'>{l}</div></div>", unsafe_allow_html=True)
    st.write("")
    a, b = st.columns(2)
    with a:
        st.markdown("<div class='sh-title' style='font-weight:700;margin-bottom:.5rem'>Applications by position</div>", unsafe_allow_html=True)
        g = df.groupby("position").agg(applications=("name", "count"), avg=("score", "mean")).reset_index()
        st.altair_chart(alt.Chart(g).mark_bar(color=ACCENT, cornerRadiusEnd=5, size=22).encode(
            y=alt.Y("position:N", sort="-x", title=None), x=alt.X("applications:Q", title=None),
            tooltip=["position", "applications", alt.Tooltip("avg:Q", format=".0f")]).properties(height=250), width="stretch")
    with b:
        st.markdown("<div class='sh-title' style='font-weight:700;margin-bottom:.5rem'>Score distribution</div>", unsafe_allow_html=True)
        st.altair_chart(alt.Chart(df).mark_bar(color=ACCENT, cornerRadiusEnd=5).encode(
            x=alt.X("score:Q", bin=alt.Bin(step=10, extent=[0, 100]), title="Score out of 100"),
            y=alt.Y("count()", title=None)).properties(height=250), width="stretch")
    st.markdown("<div class='sh-title' style='font-weight:700;margin:.8rem 0 .5rem'>Latest applications</div>", unsafe_allow_html=True)
    for _, r in df.sort_values("date", ascending=False).head(5).iterrows():
        c, label = tone(r.score)
        st.markdown(f"<div class='card' style='display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem'>"
                    f"<div><b>{r['name']}</b><br><span style='color:#667085;font-size:.85rem'>{r.position} · {r.date:%d %b}</span></div>"
                    f"<div style='text-align:right'><b style='color:{c};font-size:1.2rem'>{r.score}</b><br><span style='font-size:.8rem;color:#667085'>{label}</span></div></div>",
                    unsafe_allow_html=True)

elif page == "Candidates":
    header("Candidates", "Filter screened applicants and open any report.")
    f1, f2, f3 = st.columns([2, 2, 3])
    pos_f = f1.selectbox("Position", ["All positions"] + sorted(df.position.unique()))
    min_s = f2.slider("Minimum score", 0, 100, 0, 5)
    q = f3.text_input("Search by name or email", placeholder="Type a name or email")
    v = df[df.score >= min_s]
    if pos_f != "All positions":
        v = v[v.position == pos_f]
    if q:
        v = v[v.name.str.contains(q, case=False) | v.email.str.contains(q, case=False)]
    v = v.sort_values("score", ascending=False).reset_index(drop=True)
    st.dataframe(v[["name", "position", "score", "date", "status"]], hide_index=True, width="stretch",
                 on_select="rerun", selection_mode="single-row", key="tbl", column_config={
                     "name": "Candidate", "position": "Position", "date": st.column_config.DateColumn("Applied", format="DD MMM YYYY"),
                     "score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"), "status": "Decision"})
    sel = st.session_state.get("tbl", {}).get("selection", {}).get("rows", [])
    if not len(v):
        st.info("No candidates match these filters. Lower the minimum score or clear the search.")
    elif not sel:
        st.caption("Select a row to open the full screening report.")
    else:
        r = v.iloc[sel[0]]
        color, label = tone(r.score)
        st.write("")
        l, m, rt = st.columns([1.1, 2, 2])
        with l:
            st.markdown(f"<div class='card' style='text-align:center'><div class='ring' style='--p:{r.score};--c:{color};margin:0 auto .8rem'><span>{r.score}</span></div>"
                        f"<b style='color:{color}'>{label}</b><br><span style='color:#667085;font-size:.85rem'>{r['name']}<br>{r.position}</span></div>", unsafe_allow_html=True)
            if st.button("Shortlist", type="primary", width="stretch"):
                webhook("shortlist", {"candidate": r["name"], "email": r.email, "position": r.position})
            if st.button("Reject", width="stretch"):
                webhook("reject", {"candidate": r["name"], "email": r.email, "position": r.position})
        with m:
            html = "<div class='card'><b>Score breakdown</b>"
            for k, val in (r.params or {}).items():
                html += f"<div class='prow'><span>{k}</span><b>{val}</b></div><div class='bar'><i style='width:{val}%'></i></div>"
            if not r.params:
                html += "<p style='color:#667085'>No parameter scores stored for this candidate.</p>"
            st.markdown(html + "</div>", unsafe_allow_html=True)
        with rt:
            html = "<div class='card'><b>Required skills (out of 10)</b>"
            for k, val in (r.skills or {}).items():
                html += f"<div class='prow'><span>{k}</span><b>{val}/10</b></div><div class='bar'><i style='width:{val * 10}%'></i></div>"
            if r.missing or r.partial:
                html += "<div style='margin-top:1rem'>" + "".join(f"<span class='chip miss'>Missing: {s}</span>" for s in r.missing) \
                        + "".join(f"<span class='chip part'>Partial: {s}</span>" for s in r.partial) + "</div>"
            if not r.skills:
                html += "<p style='color:#667085'>No per-skill scores stored for this candidate.</p>"
            st.markdown(html + "</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='card' style='margin-top:1rem'><b>Screening report</b><div class='report' style='margin-top:.6rem'>{r.report}</div></div>", unsafe_allow_html=True)

else:
    header("Positions", "Open or close hiring and keep vacancy counts current.")
    cols = st.columns(3)
    for i, p in enumerate(positions):
        with cols[i % 3]:
            cls = "open" if p["status"] == "Open" else "closed"
            n = int((df.position == p["title"]).sum())
            st.markdown(f"<div class='card' style='margin-bottom:.6rem'><div style='display:flex;justify-content:space-between;align-items:center'>"
                        f"<b style='font-size:1.05rem'>{p['title']}</b><span class='pill {cls}'>{p['status']}</span></div>"
                        f"<div style='color:#667085;font-size:.88rem;margin:.6rem 0'>{p['vacancies']} vacancies · {p['priority']} priority · {n} applications</div></div>",
                        unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            if c1.button("Close" if p["status"] == "Open" else "Reopen", key=f"t{i}", width="stretch"):
                p["status"] = "Closed" if p["status"] == "Open" else "Open"
                webhook("set_position_status", {"position": p["title"], "status": p["status"]})
                st.rerun()
            p["vacancies"] = c2.number_input("Vacancies", 0, 50, int(p["vacancies"]), key=f"v{i}", label_visibility="collapsed")
