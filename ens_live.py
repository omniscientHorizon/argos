import json
import streamlit as st
from web3 import Web3
from ens import ENS

REGISTRY_7930 = "0x000100000101148004a169fb4a3325136eb29fa0ceb6d2e539a432"
_DEFAULT_RPC = "https://ethereum-rpc.publicnode.com"

@st.cache_resource(show_spinner=False)
def _ens():
    try:
        rpc = st.secrets.get("ARGOS_RPC", _DEFAULT_RPC)
    except Exception:
        rpc = _DEFAULT_RPC
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 15}))
    return ENS.from_web3(w3)

def declared_ens_names(reg_json: str):
    names = []
    try:
        j = json.loads(reg_json)
        for s in (j.get("services") or []):
            if str(s.get("name", "")).upper() == "ENS":
                ep = str(s.get("endpoint", "")).strip().lower()
                if ep.endswith(".eth"):
                    names.append(ep)
    except Exception:
        pass
    return names

@st.cache_data(ttl=3600, show_spinner=False)
def verify_ens(agent_id: int, name: str) -> dict:
    """
    Live ENSIP-25 check. Returns {"status": ..., "value": ...}.
    status: 'verified' | 'unverified' | 'no-resolver' | 'error'
    Verified = the ENS name's owner set agent-registration[<registry>][<id>],
    proving the same party controls both the name and the agent (anti-Sybil).
    """
    key = f"agent-registration[{REGISTRY_7930}][{agent_id}]"
    try:
        val = _ens().get_text(name, key)
        if val and str(val).strip():
            return {"status": "verified", "value": str(val)}
        return {"status": "unverified", "value": ""}
    except Exception as e:
        nm = type(e).__name__
        return {"status": "no-resolver" if "Resolver" in nm else "error", "value": nm}

def ens_badge_html(agent_id: int, reg_json: str) -> str:
    out = []
    for nm in declared_ens_names(reg_json):
        v = verify_ens(int(agent_id), nm)
        if v["status"] == "verified":
            out.append(
                f"<span style='background:#DCFCE7;color:#166534;padding:2px 9px;"
                f"border-radius:999px;font-size:12px;font-weight:700'>✓ ENS-verified · {nm}</span>"
            )
        else:
            label = {"no-resolver": "no resolver", "error": "unresolved"}.get(v["status"], "unverified")
            out.append(
                f"<span style='background:#F1F5F9;color:#475569;padding:2px 9px;"
                f"border-radius:999px;font-size:12px'>⌁ claims {nm} · {label}</span>"
            )
    return " ".join(out)