import argparse
import json
import os
import numpy as np
import pandas as pd

TAGS = {
    "0x90dbee9d87d6440c27c601f81cfd9aeb695431649e047fe43e7105512264b578": "trust",
    "0xf32a9c3077a9b8e2ccb97670cf9722e808c2460acba29dc22f29ebc72c4604f1": "liveness",
    "0xfb6c6c3c0d5d33f0360426b0b58d3bad994edb94748fa7bd09e73c42d811fb30": "quality",
    "0x78e1e3307b96bc9e3a8218e03b133d8df84bb8c7c94a9e8b009203253ba39b29": "reachable",
    "0xd6be4ef8f6e81499fcacb6176a8acae193c21b062774e32379bf3b823e83bd19": "starred",
    "0xd2d827af457cf64156642e178a359c554f7e701b96401ee9d0ebe3bcf325a527": "responseTime",
    "0x0c64da3764320ce6d9d2191635f418a025b0d4357e8329a8d9baf5bf3ff05d5b": "helpful",
    "0xf1e9f0e4224e5a98aaf35bb8f2017fcf1d1229d1516f638400907d50fac1bf99": "helpful",
    "0x7aa61f7d41f5fab2b7227198d10b8e1d66c06c49409fec49270e545030a3cdfb": "review",
    "0xd68a06d1c30622ddca0c9e289a7228d6719cfbf73352f467b93b2110d32342d6": "successRate",
    "0x263162b25514e5a51281ed4797f756b2d887d119c9c0f797e00e588b50363fc6": "x402",
    "0x08030e71665ed68c05a89d5970bbea7f25de43341480c9169469e06d33186249": "reliability",
    "0xfbd48ce6a90a8e8ae8fb90dc768499accb7c03c6127003e882a3b3af28cd8fa8": "uptime",
    "0xbcc8acaad6f81805673bdd7232014bcea368c964127c3c7fa373c10f21b739a9": "rating",
    "0xfc56d60e2673ff4d0153a38470f3eee3bd706beb27296af9527af376772d03ec": "accuracy",
}

def parse_json_safe(x):
    if not isinstance(x, str) or not x.strip():
        return {}
    try:
        return json.loads(x)
    except Exception:
        return {}

def mget(d, *aliases):
    """Case-insensitive key lookup with aliases (x402Support/x402support, supportedTrust/supportedTrusts)."""
    if not isinstance(d, dict):
        return None
    low = {k.lower(): v for k, v in d.items()}
    for a in aliases:
        if a.lower() in low:
            return low[a.lower()]
    return None

def mhas(d, *aliases):
    if not isinstance(d, dict):
        return False
    low = {k.lower() for k in d.keys()}
    return any(a.lower() in low for a in aliases)

def uri_scheme(uri):
    if not isinstance(uri, str) or not uri.strip():
        return "missing"
    u = uri.lower()
    if u.startswith("data:application/json;base64,"):
        return "base64_onchain"
    if u.startswith("ipfs://"):
        return "ipfs"
    if u.startswith("https://"):
        return "https"
    if u.startswith("http://"):
        return "http"
    return "other"

def list_to_pipe(x):
    if isinstance(x, list):
        return "|".join(str(i) for i in x)
    return ""

def services_to_names(x):
    if not isinstance(x, list):
        return ""
    names = []
    for item in x:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item.get("name")))
    return "|".join(names)

def services_to_endpoints(x):
    if not isinstance(x, list):
        return ""
    endpoints = []
    for item in x:
        if isinstance(item, dict) and item.get("endpoint"):
            endpoints.append(str(item.get("endpoint")))
    return "|".join(endpoints)

def clean_feedback(feedback_csv):
    fb = pd.read_csv(feedback_csv)

    fb["agent_id"] = pd.to_numeric(fb["agent_id"], errors="coerce")
    fb["score"] = pd.to_numeric(fb["score"], errors="coerce")

    fb["feedback_ts"] = pd.to_datetime(
        fb["block_timestamp"],
        utc=True,
        errors="coerce"
    )

    fb["feedback_date"] = fb["feedback_ts"].dt.date
    fb["feedback_hour"] = fb["feedback_ts"].dt.floor("h")

    fb["dim"] = fb["tag_hash"].map(TAGS).fillna("other")

    cols = [
        "agent_id",
        "client",
        "tag_hash",
        "dim",
        "score",
        "block_timestamp",
        "feedback_ts",
        "feedback_date",
        "feedback_hour",
    ]

    existing = [c for c in cols if c in fb.columns]
    fb = fb[existing].sort_values(["agent_id", "feedback_ts"])

    return fb

def clean_agents(agents_csv):
    ag = pd.read_csv(agents_csv)

    ag["agent_id"] = pd.to_numeric(ag["agent_id"], errors="coerce")
    ag["registered_at_ts"] = pd.to_datetime(
        ag["registered_at"],
        utc=True,
        errors="coerce"
    )

    ag = (
        ag.sort_values("registered_at_ts")
          .drop_duplicates("agent_id", keep="last")
          .copy()
    )

    meta = ag["reg_json"].apply(parse_json_safe)

    ag["uri_scheme"] = ag["agent_uri"].apply(uri_scheme)

    ag["metadata_parse_ok"] = ag["reg_json"].apply(
        lambda x: isinstance(x, str) and bool(x.strip())
    ) & meta.apply(lambda d: isinstance(d, dict) and len(d) > 0)

    ag["metadata_keys"] = meta.apply(
        lambda d: "|".join(sorted(d.keys())) if isinstance(d, dict) else ""
    )

    ag["reg_name"] = meta.apply(lambda d: d.get("name"))
    ag["reg_description"] = meta.apply(lambda d: d.get("description"))

    X402 = ("x402Support", "x402support", "x402_support")
    ag["x402_present"] = meta.apply(lambda d: mhas(d, *X402))
    ag["x402_value"] = meta.apply(lambda d: mget(d, *X402) if mhas(d, *X402) else np.nan)
    ag["x402_status"] = np.select(
        [
            ag["x402_present"] & (ag["x402_value"] == True),
            ag["x402_present"] & (ag["x402_value"] == False),
            ~ag["x402_present"],
        ],
        ["true", "false", "undeclared"],
        default="unknown"
    )

    ag["active_present"] = meta.apply(lambda d: "active" in d)
    ag["active_value"] = meta.apply(lambda d: d.get("active") if "active" in d else np.nan)
    ag["active_status"] = np.select(
        [
            ag["active_present"] & (ag["active_value"] == True),
            ag["active_present"] & (ag["active_value"] == False),
            ~ag["active_present"],
        ],
        ["true", "false", "undeclared"],
        default="unknown"
    )

    ag["supportedTrust_raw"] = meta.apply(lambda d: mget(d, "supportedTrust", "supportedTrusts", "supported_trust"))
    ag["supportedTrust"] = ag["supportedTrust_raw"].apply(list_to_pipe)

    ag["services_raw"] = meta.apply(lambda d: d.get("services"))
    ag["service_names"] = ag["services_raw"].apply(services_to_names)
    ag["service_endpoints"] = ag["services_raw"].apply(services_to_endpoints)

    ag["registrations_raw"] = meta.apply(lambda d: d.get("registrations"))

    cols = [
        "agent_id",
        "owner",
        "agent_uri",
        "uri_scheme",
        "registered_at",
        "registered_at_ts",
        "fully_onchain",
        "reg_json",
        "metadata_parse_ok",
        "metadata_keys",
        "reg_name",
        "reg_description",
        "x402_present",
        "x402_value",
        "x402_status",
        "active_present",
        "active_value",
        "active_status",
        "supportedTrust",
        "service_names",
        "service_endpoints",
    ]

    existing = [c for c in cols if c in ag.columns]
    ag = ag[existing].sort_values("agent_id")

    return ag

def print_basic_summary(name, df):
    print("\n" + "=" * 80)
    print(name)
    print("=" * 80)

    print(f"\nshape: {df.shape}")

    print("\ncolumns:")
    print(list(df.columns))

    print("\ndtypes:")
    print(df.dtypes)

    print("\nnull counts:")
    print(df.isna().sum().sort_values(ascending=False))

    print("\nhead:")
    print(df.head(10).to_string(index=False))

    print("\nnumeric summary:")
    numeric = df.select_dtypes(include=[np.number])
    if len(numeric.columns) > 0:
        print(numeric.describe(percentiles=[0.25, 0.5, 0.75, 0.9, 0.95, 0.99]).round(3).to_string())
    else:
        print("No numeric columns.")

    print("\nobject/category summary:")
    obj = df.select_dtypes(exclude=[np.number])
    if len(obj.columns) > 0:
        print(obj.describe().to_string())
    else:
        print("No object columns.")

def print_domain_summary(agents, feedback, joined):
    print("\n" + "=" * 80)
    print("DOMAIN SUMMARY")
    print("=" * 80)

    total_agents = agents["agent_id"].nunique()
    feedback_agents = feedback["agent_id"].nunique()
    no_feedback = total_agents - feedback_agents

    print(f"\ntotal agents: {total_agents:,}")
    print(f"agents with feedback: {feedback_agents:,}")
    print(f"agents with no feedback: {no_feedback:,}")
    print(f"pct no feedback: {100 * no_feedback / total_agents:.2f}%")

    print("\nfeedback dimensions:")
    print(feedback["dim"].value_counts(dropna=False).to_string())

    print("\nraw score summary by dimension:")
    print(
        feedback.groupby("dim")["score"]
        .agg(
            n="count",
            min="min",
            p25=lambda s: s.quantile(0.25),
            median="median",
            mean="mean",
            p75=lambda s: s.quantile(0.75),
            max="max",
            std="std",
        )
        .round(2)
        .sort_values("n", ascending=False)
        .to_string()
    )

    print("\nagent URI schemes:")
    print(agents["uri_scheme"].value_counts(dropna=False).to_string())

    print("\nx402 status:")
    print(agents["x402_status"].value_counts(dropna=False).to_string())

    print("\nactive status:")
    print(agents["active_status"].value_counts(dropna=False).to_string())

    print("\nmetadata parse ok:")
    print(agents["metadata_parse_ok"].value_counts(dropna=False).to_string())

    print("\nfully_onchain:")
    if "fully_onchain" in agents.columns:
        print(agents["fully_onchain"].value_counts(dropna=False).to_string())

    print("\ntop supportedTrust values:")
    trust_vals = (
        agents["supportedTrust"]
        .fillna("")
        .str.split("|")
        .explode()
    )
    trust_vals = trust_vals[trust_vals != ""]
    if len(trust_vals) > 0:
        print(trust_vals.value_counts().head(20).to_string())
    else:
        print("No supportedTrust values found.")

    print("\ntop service names:")
    service_vals = (
        agents["service_names"]
        .fillna("")
        .str.split("|")
        .explode()
    )
    service_vals = service_vals[service_vals != ""]
    if len(service_vals) > 0:
        print(service_vals.value_counts().head(20).to_string())
    else:
        print("No service names found.")

    print("\njoined sample:")
    print(joined.head(10).to_string(index=False))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--feedback", default="datasets/query1.csv")
    parser.add_argument("--agents", default="datasets/query2.csv")
    parser.add_argument("--outdir", default="datasets")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    feedback = clean_feedback(args.feedback)
    agents = clean_agents(args.agents)

    joined = feedback.merge(
        agents,
        on="agent_id",
        how="left",
        suffixes=("_feedback", "_agent")
    )

    feedback_out = os.path.join(args.outdir, "base_feedback_clean.csv")
    agents_out = os.path.join(args.outdir, "base_agents_clean.csv")
    joined_out = os.path.join(args.outdir, "base_agent_feedback_join.csv")

    feedback.to_csv(feedback_out, index=False)
    agents.to_csv(agents_out, index=False)
    joined.to_csv(joined_out, index=False)

    print_basic_summary("BASE FEEDBACK CLEAN — one row per feedback event", feedback)
    print_basic_summary("BASE AGENTS CLEAN — one row per registered agent", agents)
    print_basic_summary("BASE AGENT FEEDBACK JOIN — feedback + agent metadata", joined)
    print_domain_summary(agents, feedback, joined)

    print("\n" + "=" * 80)
    print("SAVED FILES")
    print("=" * 80)
    print(feedback_out)
    print(agents_out)
    print(joined_out)


if __name__ == "__main__":
    main()