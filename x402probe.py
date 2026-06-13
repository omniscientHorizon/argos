import os, time, requests, pandas as pd

from dotenv import load_dotenv

load_dotenv()

ETHERSCAN_KEY = os.getenv("ETHERSCAN_KEY")
BASE = "https://api.etherscan.io/v2/api"
"""
check_agentwallet.py — MEASURE how many agents set a custom agentWallet vs.
just using their owner address. Answers "how do I know almost nobody set one?"
empirically instead of by assertion.

Calls IdentityRegistry.getAgentWallet(agentId) for a sample of agents and
compares to owner. Reuses your Etherscan V2 key (eth_call via proxy module).

Run:  export ETHERSCAN_KEY=...   then   python check_agentwallet.py
"""

IDENTITY = "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432"   # mainnet IdentityRegistry
SELECTOR = "0x00339509"                                    # getAgentWallet(uint256)
SAMPLE   = 1651                                             # how many agents to check

def get_agent_wallet(agent_id):
    data = SELECTOR + f"{int(agent_id):064x}"
    p = dict(chainid=1, module="proxy", action="eth_call",
             to=IDENTITY, data=data, tag="latest", apikey=ETHERSCAN_KEY)
    try:
        res = requests.get(BASE, params=p, timeout=30).json().get("result", "")
    except Exception:
        return None
    if not isinstance(res, str) or len(res) < 42:
        return None
    return "0x" + res[-40:].lower()        

def main():
    df = pd.read_csv("datasets/argos.csv", low_memory=False)

    rated = df[df.feedback_count > 0]
    pool = pd.concat([rated, df]).drop_duplicates("agent_id").head(SAMPLE)

    same = custom = zero = err = 0
    customs = []
    for i, (_, a) in enumerate(pool.iterrows(), 1):
        owner = str(a.get("owner","")).lower()
        w = get_agent_wallet(a.agent_id)
        if w is None:
            err += 1
        elif w == "0x0000000000000000000000000000000000000000":
            zero += 1
        elif w == owner:
            same += 1
        else:
            custom += 1
            customs.append((int(a.agent_id), a.get("name"), w))
        if i % 25 == 0:
            print(f"  checked {i}/{len(pool)} ...")
        time.sleep(0.22)

    n = same + custom + zero
    print("\n================  RESULT  ================")
    print(f"agents checked:            {len(pool)}")
    print(f"agentWallet == owner:      {same}  ({same/max(n,1)*100:.1f}%)")
    print(f"custom agentWallet set:    {custom}  ({custom/max(n,1)*100:.1f}%)")
    print(f"zero / cleared:            {zero}")
    print(f"errors:                    {err}")
    if customs:
        print("\nagents that DID set a custom wallet:")
        for aid, nm, w in customs:
            print(f"   {aid}  {nm}  -> {w}")

if __name__ == "__main__":
    main()