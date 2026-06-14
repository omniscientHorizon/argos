import os, csv, sys
from web3 import Web3
from ens import ENS

REGISTRY_7930 = "0x000100000101148004a169fb4a3325136eb29fa0ceb6d2e539a432"

# agent_id, declared_ens_name, feedback_count, tier: parsed from argos.csv
DECLARED = [
    (22674, "hosehead.eth", 4, "Trusted"),
    (22775, "arcabot.eth", 3, "Trusted"),
    (22691, "ganland.eth", 3, "Emerging"),
    (24163, "marvin.eth", 1, "Emerging"),
    (21963, "clawdbotatg.eth", 1, "Emerging"),
    (23203, "clophorse.eth", 0, "Unrated"),
    (24011, "megaclawd.eth", 0, "Unrated"),
    (26433, "ens-registration-agent.ses.eth", 0, "Unrated"),
    (26433, "ses.eth", 0, "Unrated"),
    (22671, "beanbotai.eth", 0, "Unrated"),
    (22680, "nexus-agi.eth", 0, "Unrated"),
    (22731, "jernau.eth", 0, "Unrated"),
    (22903, "atv.eth", 0, "Unrated"),
    (25252, "0xmadre.eth", 0, "Unrated"),
    (28211, "hodlclone.eth", 0, "Unrated"),
    (28211, "agent.hodlclone.eth", 0, "Unrated"),
    (28418, "june-nbeta.eth", 0, "Unrated"),
    (31886, "meerkatt.eth", 0, "Unrated"),
    (29149, "agent-1.eth", 0, "Unrated"),
    (29149, "agent-1.eth.xid.eth", 0, "Unrated"),
    (29149, "xid.eth", 0, "Unrated"),
]

RPC = "https://ethereum-rpc.publicnode.com"

def main():
    w3 = Web3(Web3.HTTPProvider(RPC, request_kwargs={"timeout": 20}))
    if not w3.is_connected():
        sys.exit(f"Could not connect to RPC.")
    ns = ENS.from_web3(w3)

    print(f"RPC: {RPC}\nRegistry (ERC-7930): {REGISTRY_7930}\n")
    print(f"{'agent':>7}  {'ens name':30s} {'fb':>3} {'tier':9s} {'status':10s} value")
    print("-" * 78)

    rows, verified = [], 0
    for agent_id, name, fb, tier in DECLARED:
        key = f"agent-registration[{REGISTRY_7930}][{agent_id}]"
        status, value = "unverified", ""
        try:
            val = ns.get_text(name, key)
            if val and str(val).strip():
                status, value, verified = "VERIFIED", str(val), verified + 1
        except Exception as e:
            status, value = "error", type(e).__name__
        print(f"{agent_id:>7}  {name:30s} {fb:>3} {tier:9s} {status:10s} {value}")
        rows.append(dict(agent_id=agent_id, ens_name=name, feedback_count=fb,
                         tier=tier, ensip25_status=status, record_value=value))

    uniq_agents = {r["agent_id"] for r in rows if r["ensip25_status"] == "VERIFIED"}
    print("-" * 78)
    print(f"VERIFIED: {verified} / {len(DECLARED)} name-pairs   "
          f"({len(uniq_agents)} unique agents have a live ENSIP-25 attestation)")

    with open("ens_verified.csv", "w", newline="") as f:
        wcsv = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wcsv.writeheader(); wcsv.writerows(rows)
    print("wrote ens_verified.csv")

if __name__ == "__main__":
    main()