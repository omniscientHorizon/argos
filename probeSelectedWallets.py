"""
probe_custom_wallets.py — final bounded check.
Probes the 7 RATED agents that set a dedicated agentWallet for incoming USDC
(= real payments) on Ethereum + Base. These are the only agents in the whole
registry with a payment address separable from personal funds.

Run:  export ETHERSCAN_KEY=...   then   python probe_custom_wallets.py
"""
import os, time, requests

from dotenv import load_dotenv

load_dotenv()

KEY = os.getenv("ETHERSCAN_KEY")
BASE = "https://api.etherscan.io/v2/api"
CHAINS = {
    1:    ("ethereum", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6),
    8453: ("base",     "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6),
}
# the 7 custom-wallet rated agents 
CUSTOM = [
    (9382,  "Captain Dackie",  "0xf9d1d63f362bbf1ee08ab9acb36fe74afc48d5f1"),
    (13026, "Silverback",      "0xd34411a70effbdd000c529bbf572082ffdcf1794"),
    (22674, "Hosehead",        "0xf47a6d52d638b84e8eede6a3712f54cbadd857c2"),
    (28511, "Emmet",           "0x1089e1c613db8cb91db72be4818632153e62557a"),
    (22675, "Open Meta Loom",  "0xa7d395faf5e0a77a8d42d68ea01d2336671e5f55"),
    (22778, "(unnamed 22778)", "0xd8ba61a0b0974db0ec8e325c7628470526558e9b"),
    (13445, "Gekko AI",        "0xcc28cee3a1433493de119efe8cd218ff7c0e4821"),
]

def incoming_usdc(chainid, usdc, dec, wallet):
    p = dict(chainid=chainid, module="account", action="tokentx",
             contractaddress=usdc, address=wallet, page=1, offset=10000,
             sort="asc", apikey=KEY)
    try:
        r = requests.get(BASE, params=p, timeout=30).json()
    except Exception:
        return 0, 0, 0.0
    if r.get("status") != "1" or not isinstance(r.get("result"), list):
        return 0, 0, 0.0
    payers, n, vol = set(), 0, 0.0
    w = wallet.lower()
    for tx in r["result"]:
        if tx.get("to","").lower() == w:
            payers.add(tx.get("from","").lower()); n += 1
            vol += int(tx.get("value",0)) / 10**dec
    return len(payers), n, round(vol,2)

print(f'{"agent":18} {"chain":9} {"payers":>7} {"payments":>9} {"USDC in":>12}')
print("-"*60)
grand = 0
for aid, name, wallet in CUSTOM:
    for cid,(label,usdc,dec) in CHAINS.items():
        p,n,v = incoming_usdc(cid, usdc, dec, wallet)
        if n: grand += p
        print(f'{name[:18]:18} {label:9} {p:>7} {n:>9} {v:>12,.2f}')
        time.sleep(0.25)
    print("-"*60)

print(f'\n>>> total distinct payers across all 7 dedicated wallets: {grand}')
