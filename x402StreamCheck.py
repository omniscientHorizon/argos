"""
x402_stream_rpc.py — pull the x402 payment graph on Base via a FREE public RPC
(no Etherscan key; Etherscan's free tier doesn't support Base).

x402 = EIP-3009 authorized USDC transfers, identified by the AuthorizationUsed
event. We pull those, decode payer->recipient->amount, rank recipients by
distinct payers, and flag matches to your ERC-8004 agents.

Run:  python x402_stream_rpc.py
"""
import time, requests, pandas as pd
from collections import defaultdict

# free public Base RPCs — if one rate-limits/errors, swap to another:
#   https://base-rpc.publicnode.com  |  https://base.llamarpc.com  |  https://mainnet.base.org  |  https://base.drpc.org
RPC_URL = "https://base-rpc.publicnode.com"

USDC = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
AUTH_USED = "0x98de503528ee59b575ef0c0a2576a82497bfc029a5685b209e9ec333479b10a5"
SEL_TWA, SEL_RWA = "e3ee160e", "ef55bec6"     # transfer/receiveWithAuthorization
WINDOW_BLOCKS = 10000      # ~1.5 days (Base ~2s blocks). Start 10000 to test.
CHUNK         = 1500       # blocks per getLogs; lower if RPC complains
MAX_TXNS      = 3000

def rpc(method, params):
    try:
        r = requests.post(RPC_URL, json={"jsonrpc":"2.0","id":1,"method":method,"params":params}, timeout=40).json()
        return r.get("result")
    except Exception:
        return None

def latest_block():
    return int(rpc("eth_blockNumber", []), 16)

def get_auth_txhashes(frm, to):
    hashes, b = [], frm
    while b <= to:
        end = min(b+CHUNK-1, to)
        logs = rpc("eth_getLogs", [{"address": USDC, "topics": [AUTH_USED],
                    "fromBlock": hex(b), "toBlock": hex(end)}])
        if isinstance(logs, list):
            hashes += [lg["transactionHash"] for lg in logs]
        print(f"  scanned through block {end}  ({len(hashes)} x402 events so far)")
        time.sleep(0.15)
        b = end + 1
    return list(dict.fromkeys(hashes))

def decode_payment(txhash):
    tx = rpc("eth_getTransactionByHash", [txhash]) or {}
    inp = tx.get("input","")
    if len(inp) < 10+64*3: return None
    if inp[2:10] not in (SEL_TWA, SEL_RWA): return None
    payer     = "0x"+inp[10:74][-40:].lower()
    recipient = "0x"+inp[74:138][-40:].lower()
    value     = int(inp[138:202], 16)/1e6
    return payer, recipient, value

def main():
    tip = latest_block()
    frm = tip - WINDOW_BLOCKS
    print(f"scanning blocks {frm}..{tip} on Base for x402 (AuthorizationUsed) ...")
    hashes = get_auth_txhashes(frm, tip)
    print(f"found {len(hashes)} x402 txns; decoding up to {MAX_TXNS} ...")

    payers, pays, vol = defaultdict(set), defaultdict(int), defaultdict(float)
    for i,h in enumerate(hashes[:MAX_TXNS],1):
        d = decode_payment(h)
        if d: payers[d[1]].add(d[0]); pays[d[1]]+=1; vol[d[1]]+=d[2]
        if i % 100 == 0: print(f"  decoded {i} ...")
        time.sleep(0.12)

    out = pd.DataFrame([{"recipient":r,"distinct_payers":len(payers[r]),
                         "payments":pays[r],"usdc_volume":round(vol[r],2)} for r in payers]
                      ).sort_values("distinct_payers", ascending=False)
    # match to your agents
    try:
        df = pd.read_csv("datasets/argos.csv", low_memory=False)
        w = {str(a.owner).lower(): (a.get("name") or f"#{int(a.agent_id)}")
             for _,a in df.iterrows() if str(a.get("owner","")).startswith("0x")}
        w.update({"0xf9d1d63f362bbf1ee08ab9acb36fe74afc48d5f1":"Captain Dackie",
                  "0xd34411a70effbdd000c529bbf572082ffdcf1794":"Silverback",
                  "0xf47a6d52d638b84e8eede6a3712f54cbadd857c2":"Hosehead",
                  "0xcc28cee3a1433493de119efe8cd218ff7c0e4821":"Gekko AI"})
        out["agent"] = out["recipient"].map(w)
    except Exception:
        out["agent"] = None
    out.to_csv("x402_recipients.csv", index=False)
    print("\n== TOP x402 RECIPIENTS BY DISTINCT PAYERS ==")
    print(out.head(25).to_string(index=False))
    m = out[out["agent"].notna()]
    print(f"\n>>> x402 recipients matching your agents: {len(m)}")
    if len(m): print(m.head(20).to_string(index=False))
    print(f"\nsaved -> x402_recipients.csv  ({len(out)} unique recipients)")

if __name__ == "__main__":
    main()