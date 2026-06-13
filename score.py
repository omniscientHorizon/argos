import argparse
import numpy as np
import pandas as pd

M_PRIOR = 5
MIN_REVIEWERS = 3       
MIN_DIM_AGENTS = 20     
SYBIL_DIVERSITY = 0.5
BURST_NORMAL = 0.40

WEIGHTS = {"effective_reputation": 0.60, "x402": 0.20, "metadata_complete": 0.15, "freshness": 0.05}
POSITIVE_DIMS = ["trust", "quality", "starred", "helpful", "successRate", "reliability", "rating"]
HEALTH_FLAGS  = ["liveness", "reachable", "uptime"]

def load_clean(feedback_csv, agents_csv):
    fb = pd.read_csv(feedback_csv)
    ag = pd.read_csv(agents_csv)
    fb["feedback_ts"] = pd.to_datetime(fb["feedback_ts"], utc=True, errors="coerce")
    fb["score"] = pd.to_numeric(fb["score"], errors="coerce")
    if "dim" not in fb.columns:
        raise ValueError("base_feedback_clean.csv missing 'dim' — run make_base_dataset.py first")
    ag["registered_at_ts"] = pd.to_datetime(ag.get("registered_at_ts", ag.get("registered_at")), utc=True, errors="coerce")
    for c in ["x402_status", "active_status", "uri_scheme"]:   
        if c in ag.columns: ag[c] = ag[c].astype(str).str.lower()
    return fb, ag

def assemble_base(fb, ag):
    ag = ag.copy()
    ag["name"]        = ag.get("reg_name")
    ag["description"] = ag.get("reg_description")
    ag["x402_bool"]   = ag["x402_status"].eq("true")
    ag["active_bool"] = ag["active_status"].eq("true")
    name_ok   = ag["reg_name"].fillna("").astype(str).str.len() > 0
    desc_ok   = ag["reg_description"].fillna("").astype(str).str.len() > 0
    active_dc = ag["active_status"].ne("undeclared")         
    ag["meta_complete"] = (name_ok.astype(int) + desc_ok.astype(int) + active_dc.astype(int)) / 3 * 100
    ag["n_services"]    = ag["service_names"].fillna("").apply(lambda s: 0 if s == "" else len(s.split("|")))

    grp = fb.groupby("agent_id")
    feat = pd.DataFrame({
        "feedback_count": grp.size(),
        "unique_clients": grp["client"].nunique(),
        "naive_avg":      grp["score"].mean().round(2),   
    })
    feat["diversity"] = (feat["unique_clients"] / feat["feedback_count"]).clip(0, 1).round(3)

    pos  = fb[fb["dim"].isin(POSITIVE_DIMS)]
    dims = pos.pivot_table(index="agent_id", columns="dim", values="score", aggfunc="mean").add_prefix("dim_")

    health = fb[fb["dim"].isin(HEALTH_FLAGS)].pivot_table(index="agent_id", columns="dim", values="score", aggfunc="mean")
    hf = pd.DataFrame(index=health.index)
    if "liveness" in health:  hf["is_live"]      = health["liveness"] >= 50
    if "reachable" in health: hf["is_reachable"] = health["reachable"] >= 0.5

    hour = fb["feedback_hour"] if "feedback_hour" in fb.columns else fb["feedback_ts"].dt.floor("h")
    tmp  = pd.DataFrame({"agent_id": fb["agent_id"], "hour": hour})
    peak = tmp.groupby(["agent_id", "hour"]).size().groupby("agent_id").max()
    tot  = fb.groupby("agent_id").size()
    burst = (peak / tot).reindex(tot.index).fillna(0).clip(0, 1)
    feat["burst"] = burst.round(3)
    feat["burst_excess"] = ((burst - BURST_NORMAL) / (1 - BURST_NORMAL)).clip(0, 1).round(3)
    now = fb["feedback_ts"].max()
    feat["days_since_last"] = ((now - grp["feedback_ts"].max()).dt.total_seconds() / 86400).round(1)

    df = ag.set_index("agent_id").join(feat).join(dims).join(hf).reset_index()
    df["feedback_count"] = df["feedback_count"].fillna(0).astype(int)
    df["unique_clients"] = df["unique_clients"].fillna(0).astype(int)
    now2 = max(now, ag["registered_at_ts"].max())
    df["days_since_registration"] = ((now2 - df["registered_at_ts"]).dt.total_seconds() / 86400).round(1)

    df["has_reputation"]   = df["feedback_count"] > 0
    df["onchain_metadata"] = df["fully_onchain"].fillna(False) if "fully_onchain" in df else df["uri_scheme"].eq("base64_onchain")
    df["review_bucket"]    = pd.cut(df["feedback_count"], bins=[-1, 0, 1, 4, 9, np.inf], labels=["0", "1", "2-4", "5-9", "10+"])
    df["rated_dims"]       = df.filter(like="dim_").notna().sum(axis=1)
    return df

def score(df):
    df = df.copy()
    dim_cols = [c for c in df.columns if c.startswith("dim_")]

    core = [c for c in dim_cols if df[c].notna().sum() >= MIN_DIM_AGENTS] or dim_cols
    norm = pd.DataFrame(index=df.index)
    for c in core:
        lo, hi = df[c].quantile(.05), df[c].quantile(.95)
        norm[c] = ((df[c].clip(lo, hi) - lo) / (hi - lo) * 100) if hi > lo else 50.0
    df["normalized_rep"] = norm.mean(axis=1).round(1)

    # reputation exists ONLY for agents with feedback. No-feedback agents must not
    # inherit the global prior as if it were earned reputation.

    has_reviews = df["feedback_count"] > 0
    gmean = df.loc[has_reviews, "normalized_rep"].mean()
    n = df["unique_clients"]
    bayes = (n / (n + M_PRIOR)) * df["normalized_rep"].fillna(gmean) + (M_PRIOR / (n + M_PRIOR)) * gmean
    df["bayes_reputation"] = bayes.where(has_reviews)            # NaN for no-feedback
    df["confidence"] = (n / (n + 5)).round(3)                                                        
    enough = df["unique_clients"] >= MIN_REVIEWERS
    burst_excess = np.where(enough, df["burst_excess"].fillna(0), 0.0)
    cred = (df["diversity"].fillna(1.0) * (1 - burst_excess)).clip(0, 1)
    df["credibility"] = np.where(has_reviews, cred, 0.0)        
    df["credibility"] = df["credibility"].round(3)
    df["effective_reputation"] = df["bayes_reputation"].fillna(0) * df["credibility"]

    comp = pd.DataFrame(index=df.index)
    comp["effective_reputation"] = df["effective_reputation"]
    comp["x402"]                 = df["x402_bool"].fillna(False).astype(int) * 100
    comp["metadata_complete"]    = df["meta_complete"].fillna(0)
    comp["freshness"]            = (100 - np.minimum(df["days_since_last"].fillna(180), 180) / 180 * 100)
    df["agent_rank_score"] = sum(WEIGHTS[k] * comp[k] for k in WEIGHTS).clip(0, 100).round(1)

    df["flag_low_confidence"]  = df["unique_clients"] < MIN_REVIEWERS
    df["flag_possible_sybil"]  = (df["diversity"].fillna(1) < SYBIL_DIVERSITY) & (df["feedback_count"] >= 5)
    df["flag_burst"]           = (df["burst_excess"].fillna(0) > 0.5) & (df["unique_clients"] >= MIN_REVIEWERS)
    df["flag_x402_undeclared"] = df["x402_status"] == "undeclared"
    df["flag_no_reputation"]   = df["feedback_count"] == 0
    df["flag_inactive"]        = df["active_status"] == "false"

    def tier(r):
        if r["feedback_count"] == 0:                    return "Unrated"
        if r["flag_possible_sybil"] or r["flag_burst"]: return "Watchlist"
        if r["unique_clients"] >= MIN_REVIEWERS:        return "Trusted"
        return "Emerging"
    df["argos_tier"] = df.apply(tier, axis=1)
    df["search_text"] = (df["agent_id"].astype(str) + " " + df["owner"].fillna("") + " "
                         + df["name"].fillna("") + " " + df["description"].fillna("") + " "
                         + df["agent_uri"].fillna("")).str.lower()
    tier_rank = {"Trusted": 0, "Emerging": 1, "Watchlist": 2, "Unrated": 3}
    df["tier_rank"] = df["argos_tier"].map(tier_rank)
    return df.sort_values(["tier_rank", "agent_rank_score"], ascending=[True, False])


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--feedback", default="datasets/base_feedback_clean.csv")
    p.add_argument("--agents",   default="datasets/base_agents_clean.csv")
    p.add_argument("--out",      default="datasets/argos.csv")
    a = p.parse_args()

    fb, ag = load_clean(a.feedback, a.agents)

    base = assemble_base(fb, ag)
    pd.set_option("display.width", 170, "display.max_columns", 50)
    print("="*70, "\nPART 1 — BASE AGENT DATAFRAME", "\n"+"="*70)
    print(f"shape: {base.shape}")
    show = ["agent_id","name","feedback_count","unique_clients","diversity","naive_avg",
            "meta_complete","x402_status","active_status","review_bucket"]
    print("\nhead:\n", base[[c for c in show if c in base]].head().to_string(index=False))
    print("\nsummary stats:\n",
          base[["feedback_count","unique_clients","diversity","naive_avg","meta_complete","burst","days_since_last"]]
          .describe().round(2).to_string())
    print("\nfilter fields:")
    for c in ["has_reputation","onchain_metadata","x402_status","active_status","review_bucket"]:
        if c in base: print(f"  {c}: {base[c].value_counts(dropna=False).to_dict()}")

    ranked = score(base)
    ranked.to_csv(a.out, index=False)
    print("\n", "="*70, "\nPART 2 — SCORED", "\n"+"="*70)
    print("tiers:", ranked["argos_tier"].value_counts().to_dict())
    cols = ["agent_id","name","argos_tier","agent_rank_score","naive_avg","normalized_rep",
            "unique_clients","diversity","credibility","flag_possible_sybil"]
    print(ranked[ranked.feedback_count > 0][cols].head(10).to_string(index=False))
    print(f"\n-> {a.out}")