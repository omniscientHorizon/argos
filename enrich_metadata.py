import json, time, shutil, requests, pandas as pd, numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

CSV = "datasets/argos.csv"
GATEWAYS = ["https://ipfs.io/ipfs/", "https://cloudflare-ipfs.com/ipfs/", "https://dweb.link/ipfs/"]
TIMEOUT, WORKERS = 8, 16

def mget(d, *aliases):
    if not isinstance(d, dict): return None
    low = {k.lower(): v for k, v in d.items()}
    for a in aliases:
        if a.lower() in low: return low[a.lower()]
    return None

def to_url(uri):
    uri = str(uri).strip()
    if uri.startswith("ipfs://"):
        cid = uri[len("ipfs://"):]
        if cid.startswith("ipfs/"): cid = cid[5:]
        return [g + cid for g in GATEWAYS]
    if uri.startswith("http"):
        return [uri]
    return []

def fetch_json(uri):
    for url in to_url(uri):
        try:
            r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "argos/1.0"})
            if r.status_code == 200:
                return r.json()
        except Exception:
            continue
    return None

def parse_meta(d):
    if not isinstance(d, dict): return None
    x = mget(d, "x402Support", "x402support", "x402_support")
    status = "true" if x is True else ("false" if x is False else "undeclared")
    st = mget(d, "supportedTrust", "supportedTrusts", "supported_trust")
    st = "|".join(str(i) for i in st) if isinstance(st, list) else ""
    svcs = d.get("services")
    eps = "|".join(str(s.get("endpoint")) for s in svcs if isinstance(s, dict) and s.get("endpoint")) if isinstance(svcs, list) else ""
    return {"x402_status": status, "description": d.get("description") or "",
            "supportedTrust": st, "service_endpoints": eps, "name": d.get("name") or ""}

def main():
    df = pd.read_csv(CSV, low_memory=False)
    shutil.copy(CSV, "datasets/argos_backup.csv")
    targets = df[(df.feedback_count > 0) &
                 (df.uri_scheme.astype(str).isin(["https", "ipfs", "http"]))].copy()
    print(f"fetching off-chain metadata for {len(targets)} rated agents ...")

    results = {}
    def work(aid, uri):
        return aid, parse_meta(fetch_json(uri))
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(work, r.agent_id, r.agent_uri) for _, r in targets.iterrows()]
        done = 0
        for f in as_completed(futs):
            aid, meta = f.result()
            if meta: results[aid] = meta
            done += 1
            if done % 50 == 0: print(f"  {done}/{len(targets)} ...")

    changed, new_true = 0, 0
    for aid, meta in results.items():
        i = df.index[df.agent_id == aid]
        if len(i) == 0: continue
        i = i[0]
        if df.at[i, "x402_status"] != meta["x402_status"] and meta["x402_status"] == "true":
            new_true += 1
        for col in ["x402_status", "description", "supportedTrust", "service_endpoints"]:
            if meta[col]: df.at[i, col] = meta[col]
        if (not str(df.at[i, "name"]).strip()) and meta["name"]:
            df.at[i, "name"] = meta["name"]
        changed += 1

    # recompute Argos score for changed rows 
    if {"effective_reputation", "meta_complete", "days_since_last"} <= set(df.columns):
        for aid in results:
            i = df.index[df.agent_id == aid]
            if len(i) == 0: continue
            i = i[0]
            x = 100.0 if str(df.at[i, "x402_status"]).lower() == "true" else 0.0
            dsl = df.at[i, "days_since_last"]
            fresh = 100 - min(float(dsl) if pd.notna(dsl) else 180, 180) / 180 * 100
            df.at[i, "agent_rank_score"] = round(
                0.60*float(df.at[i, "effective_reputation"]) + 0.20*x +
                0.15*float(df.at[i, "meta_complete"]) + 0.05*fresh, 2)

    df.to_csv(CSV, index=False)
    print(f"\n== DONE ==")
    print(f"agents fetched OK:        {len(results)} / {len(targets)}")
    print(f"rows updated:             {changed}")
    print(f"NEW x402-payable agents:  {new_true}")
    rated = df[df.feedback_count > 0]
    print(f"rated agents now x402=true: {int((rated.x402_status.astype(str).str.lower()=='true').sum())}")
    print(f"saved -> {CSV}  (backup at datasets/argos_backup.csv)")

if __name__ == "__main__":
    main()