import json, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = "eda_output"; os.makedirs(OUT, exist_ok=True)

TAGS = { 
 "0x90dbee9d87d6440c27c601f81cfd9aeb695431649e047fe43e7105512264b578":"trust",
 "0xf32a9c3077a9b8e2ccb97670cf9722e808c2460acba29dc22f29ebc72c4604f1":"liveness",
 "0xfb6c6c3c0d5d33f0360426b0b58d3bad994edb94748fa7bd09e73c42d811fb30":"quality",
 "0x78e1e3307b96bc9e3a8218e03b133d8df84bb8c7c94a9e8b009203253ba39b29":"reachable",
 "0xd6be4ef8f6e81499fcacb6176a8acae193c21b062774e32379bf3b823e83bd19":"starred",
 "0xd2d827af457cf64156642e178a359c554f7e701b96401ee9d0ebe3bcf325a527":"responseTime",
 "0x0c64da3764320ce6d9d2191635f418a025b0d4357e8329a8d9baf5bf3ff05d5b":"helpful",
 "0xf1e9f0e4224e5a98aaf35bb8f2017fcf1d1229d1516f638400907d50fac1bf99":"helpful",   # "Helpful"
 "0x7aa61f7d41f5fab2b7227198d10b8e1d66c06c49409fec49270e545030a3cdfb":"review",
 "0xd68a06d1c30622ddca0c9e289a7228d6719cfbf73352f467b93b2110d32342d6":"successRate",
 "0x263162b25514e5a51281ed4797f756b2d887d119c9c0f797e00e588b50363fc6":"x402",
 "0x08030e71665ed68c05a89d5970bbea7f25de43341480c9169469e06d33186249":"reliability",
 "0xfbd48ce6a90a8e8ae8fb90dc768499accb7c03c6127003e882a3b3af28cd8fa8":"uptime",
 "0xbcc8acaad6f81805673bdd7232014bcea368c964127c3c7fa373c10f21b739a9":"rating",
 "0xfc56d60e2673ff4d0153a38470f3eee3bd706beb27296af9527af376772d03ec":"accuracy",
}

def hr(t): print("\n" + "="*70 + f"\n{t}\n" + "="*70)


fb = pd.read_csv("datasets/query1.csv")
ag = pd.read_csv("datasets/query2.csv")

fb["ts"]  = pd.to_datetime(fb["block_timestamp"], utc=True, errors="coerce")
fb["dim"] = fb["tag_hash"].map(TAGS).fillna("other")
fb["score"] = pd.to_numeric(fb["score"], errors="coerce")

hr("0. SHAPES + MISSINGNESS")
print(f"feedback: {fb.shape} | agents: {ag.shape}")
print("\nfeedback nulls:\n", fb.isna().sum())
print("\nagents nulls:\n", ag.isna().sum())
print(f"\nagents with NO feedback: {ag['agent_id'].nunique() - fb['agent_id'].nunique()} "
      f"({100*(1 - fb['agent_id'].nunique()/ag['agent_id'].nunique()):.1f}% empty storefronts)")

hr("1. DIMENSION SCALES")
dim_stats = (fb.groupby("dim")["score"]
               .agg(n="count", min="min", p25=lambda s: s.quantile(.25),
                    median="median", mean="mean", p75=lambda s: s.quantile(.75),
                    max="max", std="std").round(2)
               .sort_values("n", ascending=False))
print(dim_stats.to_string())

binchk = (fb.groupby("dim")["score"]
            .agg(n="count",
                 pct_0_or_1=lambda s: ((s == 0) | (s == 1)).mean() * 100,
                 pct_at_max=lambda s: (s == s.max()).mean() * 100).round(1)
            .sort_values("n", ascending=False).head(10))
print("\nBinary-ness check (high pct_0_or_1 => a 0/1 health FLAG, not a 0-100 score):")
print(binchk.to_string())
print(">> Flag-like dims (e.g. liveness/reachable) should NOT enter the quality composite as scores.")

top = dim_stats.head(6).index
fig, axes = plt.subplots(2, 3, figsize=(14, 7))

for ax, d in zip(axes.ravel(), top):
    fb.loc[fb.dim == d, "score"].hist(bins=30, ax=ax); ax.set_title(d)
fig.suptitle("Score distribution per dimension"); fig.tight_layout()
fig.savefig(f"{OUT}/1_dimension_distributions.png", dpi=110); plt.close(fig)

pivot = fb.pivot_table(index="agent_id", columns="dim", values="score", aggfunc="mean")
corr = pivot[ [c for c in top if c in pivot] ].corr().round(2)

print("\nDimension correlation (per agent):\n", corr.to_string())
print(">> High corr (>0.8) = redundant, averaging is fine. Low/negative = measure different things.")

hr("2. REVIEW-COUNT SKEWNESS")
per = fb.groupby("agent_id").agg(reviews=("score","size"),
                                 raters=("client","nunique"))
print(per.describe(percentiles=[.5,.75,.9,.95,.99]).round(1).to_string())
for k in [1,2,3,5,10]:
    print(f"  agents with >= {k:>2} unique raters: {(per.raters>=k).sum():>5} "
          f"({100*(per.raters>=k).mean():.1f}%)")
fig, ax = plt.subplots(figsize=(7,4))
per.reviews.clip(upper=per.reviews.quantile(.99)).hist(bins=40, ax=ax)
ax.set_title("Reviews per agent (clipped at p99)"); fig.tight_layout()
fig.savefig(f"{OUT}/2_reviews_per_agent.png", dpi=110); plt.close(fig)


hr("3. RATER BREADTH")
breadth = fb.groupby("client")["agent_id"].nunique()

print(breadth.describe(percentiles=[.5,.9,.99]).round(2).to_string())

single = (breadth <= 1).mean()

print(f"\n>> {100*single:.1f}% of ALL raters review only ONE agent.")

fig, ax = plt.subplots(figsize=(7,4))
breadth.clip(upper=breadth.quantile(.99)).hist(bins=30, ax=ax)
ax.set_title("Agents rated per client"); fig.tight_layout()
fig.savefig(f"{OUT}/3_rater_breadth.png", dpi=110); plt.close(fig)


hr("4. TEMPORAL CONCENTRATION")

h = fb.dropna(subset=["ts"]).copy(); h["hour"] = h["ts"].dt.floor("h")
peak = h.groupby(["agent_id","hour"]).size().groupby("agent_id").max()
tot  = fb.groupby("agent_id").size()
burst = (peak/tot).reindex(tot.index).fillna(0)
multi = burst[tot>=5]

print("Peak-hour share, agents with >=5 reviews:")
print(multi.describe(percentiles=[.5,.9,.95,.99]).round(3).to_string())

fig, ax = plt.subplots(figsize=(7,4))
fb.set_index("ts").resample("D").size().plot(ax=ax)
ax.set_title("Feedback volume per day"); fig.tight_layout()
fig.savefig(f"{OUT}/4_feedback_over_time.png", dpi=110); plt.close(fig)


hr("5. METADATA COVERAGE")
def parse(x):
    try: return json.loads(x) if isinstance(x,str) and x.strip() else {}
    except Exception: return {}

m = ag["reg_json"].apply(parse)

print(f"fully_onchain (decodable metadata): {ag['fully_onchain'].mean()*100:.1f}%")

for f in ["name","description","services","x402Support","supportedTrust","active"]:
    print(f"  has {f:<14}: {100*m.apply(lambda d: bool(d.get(f))).mean():.1f}%")

trust_vals = pd.Series([t for d in m for t in (d.get("supportedTrust") or [])])

print("\nsupportedTrust values (candidates for one-hot):")
print(trust_vals.value_counts().to_string() if len(trust_vals) else "  (none)")

print(f"\n\nDone. Figures saved to {OUT}/. ")