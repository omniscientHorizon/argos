<div align="center">

# 👁️ Argos

### Trust scores for the on-chain agent economy

**A Sybil-aware reputation and discovery engine for ERC-8004 agents.**

[Live App](https://argos0.streamlit.app/) · [ETHGlobal NY 2026](https://ethglobal.com/showcase)

</div>

## TL;DR

Most agent leaderboards rank by **average rating**. But ratings are free to fake, you could always spin up 100 wallets, rate your own agent 100, and top the board. Argos ranks ERC-8004 agents by whether their reputation is *actually trustworthy*: it weights every review by the **independence of the reviewers**, catches review farms and rating bursts, flags which agents are **x402-payable**, and verifies agent identities on-chain via **ENSIP-25**. It indexes **34,453 agents** from Ethereum mainnet and surfaces the ones you can both trust and pay.
 
## The Problem
 
[ERC-8004](https://eips.ethereum.org/EIPS/eip-8004) gives AI agents a portable, on-chain identity and a public reputation trail: an Identity Registry (ERC-721 + URIStorage) and a Reputation Registry where anyone can post feedback. 
 
**BUT Reputation is only as good as its resistance to manipulation.** On-chain feedback is permissionless, so a single operator can:
 
- Register an agent, then rate it from a swarm of fresh wallets (a Sybil attack).
- Push a burst of identical 5-star reviews in a short window (review farming).
- Inflate a raw average that any naive leaderboard will happily rank #1.
The ERC-8004 spec itself notes this in its Security Considerations and explicitly expects *"an ecosystem of specialized services for agent scoring"* to filter by reviewer. **Argos is one of those services.**

## What Argos Does
 
- **Sybil-aware trust scoring** — ranks agents by reviewer independence, not raw average.
- **Manipulation detection** — flags low-diversity feedback, rating bursts, stale/incomplete agents, and likely Sybil patterns.
- **Trustworthy & payable discovery** — surfaces agents that are both well-ranked *and* support x402 payments.
- **Live ENS identity verification** — implements ENSIP-25 to prove an agent and its `.eth` name share an owner.
- **Full transparency** — every agent card shows exactly how its score was built.
- **Search** — by name, agent id, owner address, or ENS name.

## How It Works
 
```
Ethereum mainnet logs
        │
        ▼
 Google BigQuery  ──►  raw event decoding in SQL  ──►  per-agent dataset (datasets/argos.csv)
        │                                                        │
        │                                                        ▼
        │                                              scoring pipeline (argos_score.py)
        │                                                        │
        ▼                                                        ▼
 off-chain metadata fetch (enrich_metadata.py)          Streamlit app (app.py)
 live ENSIP-25 resolution (ens_live.py)                 deployed on Streamlit Cloud
```

### 1. Data layer — Google BigQuery
 
Argos reads the raw ERC-8004 event logs directly from the public dataset
`bigquery-public-data.goog_blockchain_ethereum_mainnet_us.logs` and decodes them **entirely in SQL**.
 
| Registry | Address | Event used |
|---|---|---|
| Identity | `0x8004A169FB4a3325136EB29fA0ceB6D2e539a432` | `Registered(uint256,string,address)` — topic0 `0xca52e62c…` |
| Reputation | `0x8004BAa17C55a88189AE136b182e5fdA19dE9b63` | `NewFeedback(...)` — topic0 `0x6a4a6174…` |
 
Decoding uses `block_timestamp` partition pruning (registry launched 2026-01-28) so scans stay cheap. The pipeline:
 
- Extracts `agentId` from the indexed topic and the owner from the padded address topic.
- Decodes the `agentURI` (hex → UTF-8) and, for fully on-chain agents, the base64 `data:` registration JSON to read `x402Support`, `description`, `supportedTrust`, and declared services.
- Aggregates feedback per agent: `feedback_count`, `unique_clients`, raw average (`raw_value / 10^valueDecimals`).


 ### 2. The scoring pipeline
 
Each agent's final **Argos Score** is built in stages:
 
**Stage 1 — normalize.** Raw averages are put on a common 0–100 scale (`normalized_rep`).
 
**Stage 2 — Bayesian shrinkage.** Thin evidence is pulled toward the population mean, so 3 reviews can't masquerade as the certainty of 300. (More than half of "Trusted" agents have exactly 3 reviewers, shrinkage keeps a 100/100 from three wallets from outranking a 91w from fifty.)
 
**Stage 3 — credibility multiplier.** This is the heart of Argos. A `credibility` score in `[0,1]` is built from:
- **Reviewer diversity** — distinct wallets relative to review count.
- **Burst detection** — the share of reviews landing in a single short window.
`effective_reputation = normalized_rep × credibility`
 
A high average from a tight cluster of wallets gets multiplied down hard. 
*(Example: Gekko AI — normalized 92 × credibility 0.23 = effective reputation ≈ 20.)*
 
**Stage 4 — composite.** The final score blends effective reputation with secondary signals:
 
```
Argos Score = 0.60 · effective_reputation
            + 0.20 · x402_support          (100 if true, else 0)
            + 0.15 · metadata_completeness
            + 0.05 · freshness
 
freshness   = 100 − min(days_since_last_review, 180) / 180 · 100
```

he weights keep reputation dominant (0.60) while rewarding payable, well-documented, and active agents.
 
### 3. Tiers
 
| Tier | Definition |
|---|---|
| **Trusted** | ≥ 3 independent reviewers and no manipulation flags |
| **Emerging** | Has feedback but too few reviewers to be certain — promising, unproven |
| **Watchlist** | Flagged for a manipulation pattern (low diversity, burst, etc.) |
| **Unrated** | No on-chain feedback yet |
 
Argos treats "Trusted" as **curation, not certification**, i.e *≥3 independent reviewers with no red flags*. 
 
### 4. Manipulation flags
 
| Flag | Trigger |
|---|---|
| `flag_possible_sybil` | Low reviewer diversity (few distinct wallets) |
| `flag_burst` | A large share of reviews in a single short window |
| `flag_inactive` | Marked inactive / stale |
| `flag_low_confidence` | Very few reviewers |
| `flag_x402_undeclared` | x402 status not declared in metadata |
 
A flag signals a *coordinated pattern*, not a conviction, Argos demotes and surfaces these agents.

### 5. ENS identity verification (ENSIP-25)
 
Agents may declare an ENS name in their ERC-8004 registration (the `ENS` service endpoint). Declaring proves nothing, anyone can claim `vitalik.eth`. Argos verifies it using **[ENSIP-25](https://docs.ens.domains/ensip/25/)**, the verification standard ENS authored specifically for ERC-8004.
 
For each declared name, Argos resolves the text record:
 
```
agent-registration[<registry-ERC-7930>][<agentId>]
```
 
where `<registry-ERC-7930>` = `0x000100000101148004a169fb4a3325136eb29fa0ceb6d2e539a432`.
 
Only the **owner of the ENS name** can set that record, so its presence proves the same party controls both the agent and the name. This resolves **live, on-chain, with no hard-coded values** (`ens_live.py`). It is a cryptographic, anti-Sybil **identity** signal. Verification costs work, so it can't be cheaply faked across hundreds of agents.
 
### 6. x402 payability
 
Per the ERC-8004 spec, payments are orthogonal to the protocol but agents advertise `x402Support` in metadata. Argos flags every agent that supports x402 (joining the on-chain registration data) and surfaces a **Trustworthy & Payable** list — the answer to *"which agents can I both trust and pay?"*
 
---

*(snapshot at submission)*
 
| Metric | Value |
|---|---|
| Agents indexed | 34,453 |
| Rated agents (have feedback) | 1,651 |
| Trusted | 95 |
| Emerging | 1,536 |
| Watchlist | 20 |
| Trustworthy & payable | 310 (after off-chain enrichment) |


