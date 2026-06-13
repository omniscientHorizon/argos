import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="Argos",
    page_icon="👁️",
    layout="wide"
)

st.markdown(
"""
<style>
#MainMenu, footer, header {visibility:hidden;}
.block-container {max-width:820px; padding-top:3rem;}
.stApp {background:#ffffff;}
* {font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}
.word {text-align:center; font-size:64px; font-weight:800; letter-spacing:-2px; color:#111418; margin:0;}
.tag  {text-align:center; color:#6B7280; font-size:16px; margin:.2rem 0 1.4rem;}
.stat {text-align:center; color:#9AA3AF; font-size:13px; letter-spacing:.3px; margin-top:.4rem;}
.pill {display:inline-block; padding:3px 12px; border-radius:999px; font-size:13px; font-weight:700; color:#fff;}
.p-trusted{background:#15803D;} .p-emerging{background:#1D4ED8;}
.p-watch{background:#DC2626;} .p-unrated{background:#6B7280;}
.card {border:1px solid #E5E7EB; border-radius:16px; padding:24px 26px; margin-top:18px;
       box-shadow:0 1px 3px rgba(0,0,0,.04);}
.verdict {font-size:22px; font-weight:700; color:#111418; margin:0 0 2px;}
.big {font-size:46px; font-weight:800; color:#111418; line-height:1;}
.lab {color:#9AA3AF; font-size:12px; text-transform:uppercase; letter-spacing:.5px;}
.chip {display:inline-block; background:#F3F4F6; color:#374151; border-radius:8px;
       padding:4px 10px; font-size:13px; margin:3px 6px 3px 0;}
.flag {display:inline-block; background:#FEF2F2; color:#B91C1C; border:1px solid #FCA5A5;
       border-radius:8px; padding:3px 9px; font-size:12px; margin:3px 6px 3px 0;}
.flow {color:#374151; font-size:14px; line-height:1.9;}
.muted{color:#6B7280;}
hr {border:none; border-top:1px solid #EEF0F2; margin:1.6rem 0;}
</style>
""", 
unsafe_allow_html=True
)

PCLASS = {"Trusted":"p-trusted","Emerging":"p-emerging","Watchlist":"p-watch","Unrated":"p-unrated"}
def pill(t): return f'<span class="pill {PCLASS.get(t,"p-unrated")}">{t}</span>'

@st.cache_data
def load_data():
    df = pd.read_csv("datasets/argos.csv", low_memory=False)

    df["name"] = df["name"].fillna("")
    df["display"] = df["name"].where(
        df["name"].str.len() > 0,
        "agent #" + df["agent_id"].astype(str)
    )
    flag_cols = [
        "flag_possible_sybil",
        "flag_burst",
        "flag_x402_undeclared",
        "flag_inactive",
        "flag_low_confidence",
    ]
    for c in flag_cols:
        if c in df.columns:
            df[c] = df[c].fillna(False).astype(bool)

    if "search_text" not in df.columns:
        df["search_text"] = (
            df["agent_id"].astype(str) + " " +
            df["display"].fillna("") + " " +
            df.get("owner", "").fillna("").astype(str)
        ).str.lower()

    return df

df = load_data()
rated = df[df["feedback_count"] > 0]


def reasons(r):
    out=[]
    if r.get("flag_possible_sybil"): out.append("low reviewer diversity")
    if r.get("flag_burst"):          out.append("review burst")
    if r.get("flag_inactive"):       out.append("marked inactive")
    if r.get("flag_low_confidence"): out.append("few reviewers")
    if r.get("flag_x402_undeclared"):out.append("x402 undeclared")
    return out
 
def verdict(r):
    t=r["argos_tier"]; n=int(r["unique_clients"]); fc=int(r["feedback_count"])
    if t=="Trusted":  return f'✓ Trusted — {n} independent reviewers, no manipulation flags.'
    if t=="Emerging": return f'Emerging — only {n} reviewer{"s" if n!=1 else ""} so far. Promising but unproven.'
    if t=="Unrated":  return 'Unrated there is no on-chain feedback yet. Proceed with caution.'
    if r.get("flag_possible_sybil"): return f'⚠ Watchlist — {fc} reviews from only {n} wallets.'
    if r.get("flag_burst"):          return f'⚠ Watchlist — {n} wallets, but {r["burst"]*100:.0f}% of reviews in one hour.'
    return '⚠ Watchlist — flagged for review.'
 
def trust_card(r):
    nr  = f'{r["normalized_rep"]:.0f}' if pd.notna(r["normalized_rep"]) else "—"
    dv  = f'{r["diversity"]:.2f}' if pd.notna(r["diversity"]) else "—"
    bu  = f'{r["burst"]*100:.0f}%' if pd.notna(r["burst"]) else "—"
    rec = f'{r["days_since_last"]:.0f}d ago' if pd.notna(r.get("days_since_last")) else "—"
    chips = "".join([
        f'<span class="chip">{int(r["unique_clients"])} reviewers</span>',
        f'<span class="chip">{int(r["feedback_count"])} reviews</span>',
        f'<span class="chip">diversity {dv}</span>',
        f'<span class="chip">busiest hour {bu}</span>',
        f'<span class="chip">last review {rec}</span>',
        f'<span class="chip">x402: {r["x402_status"]}</span>',
    ])
    flags = "".join(f'<span class="flag">{x}</span>' for x in reasons(r))
    html = f'''<div class="card">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px">
        <div>
          <div class="verdict">{verdict(r)}</div>
          <div class="muted" style="font-size:14px">{r["display"]} · id {int(r["agent_id"])}</div>
        </div>
        <div style="text-align:right">{pill(r["argos_tier"])}
          <div class="big" style="margin-top:8px">{r["agent_rank_score"]:.0f}</div>
          <div class="lab">Argos score</div>
        </div>
      </div>
      <hr>
      <div class="lab" style="margin-bottom:6px">Signals</div>
      <div>{chips}</div>
      {("<div style='margin-top:10px'>"+flags+"</div>") if flags else ""}
      <hr>
      <div class="lab" style="margin-bottom:6px">How the score is built</div>
      <div class="flow">
        normalized reputation <b>{nr}</b> &nbsp;×&nbsp; credibility <b>{r["credibility"]:.2f}</b>
        &nbsp;=&nbsp; effective reputation <b>{r["effective_reputation"]:.0f}</b><br>
        &nbsp;+&nbsp; x402 / metadata / freshness &nbsp;→&nbsp; <b>Argos Score {r["agent_rank_score"]:.0f}</b>
      </div>
    </div>'''
    html = "".join(line.strip() for line in html.splitlines())
    st.markdown(html, unsafe_allow_html=True)
    if isinstance(r.get("description"), str) and r["description"]:
        st.caption(r["description"][:280])
 
st.markdown('<div class="word">argos</div>', unsafe_allow_html=True)
st.markdown('<div class="tag">trust scores for the on-chain agent economy</div>', unsafe_allow_html=True)
_, mid, _ = st.columns([1,5,1])
with mid:
    q = st.text_input("search", placeholder="search an agent by name, id, or owner…",
                      label_visibility="collapsed")
st.markdown(f'<div class="stat">{len(df):,} agents · {len(rated):,} rated · '
            f'{(df.argos_tier=="Trusted").sum()} trusted · {(df.argos_tier=="Watchlist").sum()} flagged</div>',
            unsafe_allow_html=True)
 
if q and q.strip():
    m = df[df["search_text"].fillna("").str.contains(q.strip().lower(), regex=False)]
    if len(m)==0:
        st.markdown('<div class="card"><div class="verdict">No agent found</div>'
                    '<div class="muted">Try a name, numeric id, or owner address.</div></div>', unsafe_allow_html=True)
    else:
        m = m.sort_values(["tier_rank","agent_rank_score"], ascending=[True,False]) if "tier_rank" in m \
            else m.sort_values("agent_rank_score", ascending=False)
        if len(m) > 1:
            pick = st.selectbox(f"{len(m)} matches", m["agent_id"].tolist(),
                                format_func=lambda i: f'{df.loc[df.agent_id==i,"display"].iloc[0]} (id {i})')
            trust_card(df[df.agent_id==pick].iloc[0])
        else:
            trust_card(m.iloc[0])
else:
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("###### Trusted leaderboard")
    t = df[df.argos_tier=="Trusted"].sort_values("agent_rank_score", ascending=False)
    st.dataframe(
        t[["display","agent_rank_score","unique_clients","diversity","x402_status"]].rename(
            columns={"display":"agent","agent_rank_score":"Argos","unique_clients":"reviewers","x402_status":"x402"}),
        use_container_width=True, hide_index=True)
 
    with st.expander("🚩  Flagged agents (Watchlist)"):
        w = df[df.argos_tier=="Watchlist"].copy()
        w["flags"] = w.apply(lambda r: ", ".join(reasons(r)), axis=1)
        st.dataframe(w.sort_values("naive_avg", ascending=False)[
            ["display","naive_avg","agent_rank_score","feedback_count","unique_clients","diversity","flags"]
        ].rename(columns={"display":"agent","naive_avg":"raw avg","agent_rank_score":"Argos",
                          "feedback_count":"reviews","unique_clients":"wallets"}),
        use_container_width=True, hide_index=True)
 
    with st.expander("⚖️  How Argos reorders the raw-average board"):
        pool = rated[rated.feedback_count>=5]
        a,b = st.columns(2)
        a.caption("Ranked by raw average")
        a.dataframe(pool.sort_values("naive_avg",ascending=False).head(10)[["display","naive_avg","argos_tier"]]
                    .rename(columns={"display":"agent","naive_avg":"raw"}), hide_index=True, use_container_width=True)
        b.caption("Ranked by Argos")
        b.dataframe(pool.sort_values("agent_rank_score",ascending=False).head(10)[["display","agent_rank_score","argos_tier"]]
                    .rename(columns={"display":"agent","agent_rank_score":"Argos"}), hide_index=True, use_container_width=True)
 
st.markdown('<div class="stat" style="margin-top:2rem">ERC-8004 · Ethereum mainnet via BigQuery</div>', unsafe_allow_html=True)
 


