import json, shutil, sys, os
import pandas as pd

PATH = "datasets/argos.csv" 

def declared_ens_names(reg_json, svc):
    names = set()
    try:
        j = json.loads(reg_json)
        for s in (j.get("services") or []):
            if str(s.get("name", "")).upper() == "ENS":
                ep = str(s.get("endpoint", "")).strip().lower()
                if ep.endswith(".eth"):
                    names.add(ep)
    except Exception:
        pass
    import re
    for m in re.findall(r"\b[a-z0-9][a-z0-9\-]{1,}\.eth\b", str(svc), re.I):
        names.add(m.lower())
    return names

def main():
    df = pd.read_csv(PATH, low_memory=False)
    if "search_text" not in df.columns:
        sys.exit("no search_text column found")
    shutil.copy(PATH, PATH.replace("argos.csv", "argos_backup_ens.csv"))

    updated = 0
    for i, r in df.iterrows():
        names = declared_ens_names(r.get("reg_json", ""), r.get("service_endpoints", ""))
        if not names:
            continue
        st = str(r.get("search_text", "")).lower()
        add = [n for n in names if n not in st]
        if add:
            df.at[i, "search_text"] = (st + " " + " ".join(sorted(add))).strip()
            updated += 1

    df.to_csv(PATH, index=False)
    print(f"appended ENS names into search_text for {updated} agents")
    print(f"wrote {PATH} (backup: {PATH.replace('argos.csv','argos_backup_ens.csv')})")

if __name__ == "__main__":
    main()