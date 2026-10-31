#!/usr/bin/env python3
"""compare.py - two checks over capture directories, reported per scenario.

    python compare.py --baseline DIR --candidate DIR --config regression-check.yml [--json report.json]
    python compare.py --candidate DIR --config regression-check.yml            # dependency + expected checks only

1. Regression comparison (needs --baseline): did behaviour or data change between
   the two captures? Field-level on responses and stdout summaries; row-level by
   key on snapshotted tables, with per-field tolerances from the config. Rows
   missing on either side are reported, never skipped.
2. Requirement checks (candidate alone): did each scenario use only approved
   dependencies (from call_log evidence), and do independently verified expected
   values match (expected_values files)?

A difference is tagged business / response / data / dependency / expected.
Exit: 0 clean; 1 any difference or failed check; 2 input error.
This script never edits a baseline.
"""
import argparse, json, sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("compare.py needs PyYAML")


def flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items(): out.update(flatten(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj): out.update(flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = obj
    return out

def tol_for(cfg, table, field):
    t = (cfg.get("tolerances") or {})
    return t.get(f"{table}.{field}") or t.get("default") or {"abs": 0.0}

def within(a, b, tol):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        if "rel" in tol and a != 0: return abs(a - b) / abs(a) <= tol["rel"]
        return abs(a - b) <= tol.get("abs", 0.0)
    return a == b

def rows_by_key(table):
    idx = [table["fields"].index(k) for k in table["key"]]
    out = {}
    dups = []
    for r in table["rows"]:
        k = tuple(r[i] for i in idx)
        if k in out: dups.append(k)
        out[k] = dict(zip(table["fields"], r))
    return out, dups

def is_business(field, bfields):
    return field == "status" or any(field == f"body.{b}" or field.startswith(f"body.{b}.") or field.startswith(f"body.{b}[") for b in bfields)


def compare_pair(cfg, base, cand):
    r = {"scenario": base["scenario"], "type": base.get("type"), "business": [], "response": [], "data": [], "notes": []}
    # command scenarios: stdout summary + exit code
    if "run" in base:
        bf, cf = flatten({"exit_code": base["run"]["exit_code"], "summary": base["run"]["summary"]}), \
                 flatten({"exit_code": cand.get("run", {}).get("exit_code"), "summary": cand.get("run", {}).get("summary", {})})
        for k in sorted(set(bf) | set(cf)):
            if bf.get(k, "<absent>") != cf.get(k, "<absent>"):
                r["business"].append({"field": k, "baseline": bf.get(k, "<absent>"), "candidate": cf.get(k, "<absent>")})
    # service/ui steps
    for i, bs in enumerate(base.get("steps", [])):
        cs = (cand.get("steps") or [None] * (i + 1))[i] if i < len(cand.get("steps", [])) else None
        if cs is None:
            r["response"].append({"step": i, "field": "<step>", "baseline": "present", "candidate": "<absent>"}); continue
        bresp, cresp = bs.get("response", {}), cs.get("response", {})
        bf = flatten({"status": bresp.get("status"), "body": bresp.get("body")})
        cf = flatten({"status": cresp.get("status"), "body": cresp.get("body")})
        for k in sorted(set(bf) | set(cf)):
            if bf.get(k, "<absent>") != cf.get(k, "<absent>"):
                d = {"step": i, "field": k, "baseline": bf.get(k, "<absent>"), "candidate": cf.get(k, "<absent>")}
                (r["business"] if is_business(k, bs.get("business_fields", [])) else r["response"]).append(d)
    # tables
    for tname, bt in base.get("tables", {}).items():
        ct = cand.get("tables", {}).get(tname)
        if ct is None:
            r["data"].append({"table": tname, "key": "*", "field": "<table>", "baseline": "present", "candidate": "<absent>"}); continue
        brows, bd = rows_by_key(bt); crows, cd = rows_by_key(ct)
        for k in bd: r["data"].append({"table": tname, "key": list(k), "field": "<duplicate key>", "baseline": "dup", "candidate": ""})
        for k in cd: r["data"].append({"table": tname, "key": list(k), "field": "<duplicate key>", "baseline": "", "candidate": "dup"})
        changed_keys = set()
        for k in sorted(set(brows) | set(crows), key=str):
            if k not in crows:
                r["data"].append({"table": tname, "key": list(k), "field": "<row>", "baseline": brows[k], "candidate": "<absent>"}); changed_keys.add(k)
            elif k not in brows:
                r["data"].append({"table": tname, "key": list(k), "field": "<row>", "baseline": "<absent>", "candidate": crows[k]}); changed_keys.add(k)
            else:
                for f in bt["fields"]:
                    if f in bt["key"]: continue
                    if not within(brows[k][f], crows[k][f], tol_for(cfg, tname, f)):
                        r["data"].append({"table": tname, "key": list(k), "field": f, "baseline": brows[k][f], "candidate": crows[k][f]}); changed_keys.add(k)
        if bt["key"] and changed_keys:
            first = bt["key"][0]
            groups = sorted({k[0] for k in changed_keys}, key=str)
            r["notes"].append(f"{tname}: {len(changed_keys)} row(s) differ across {len(groups)} {first}(s): {groups[:12]}{' ...' if len(groups) > 12 else ''} of {len(set(k[0] for k in brows))}")
    return r


def requirement_checks(cfg, cand, repo_root):
    """Dependency assertion + expected-value checks on one candidate capture."""
    out = {"dependency": [], "expected": []}
    approved = set(cfg.get("approved_dependencies") or [])
    if cand.get("expect_dependencies") == "approved_only":
        used = cand.get("calls", {}).get("by_service", {})
        for svc, n in used.items():
            if svc not in approved:
                out["dependency"].append({"service": svc, "calls": n, "approved": sorted(approved),
                                          "evidence": f"call_log: {n} call(s) to {svc} during scenario"})
    exp_path = next((s.get("expected_values") for s in cfg["scenarios"] if s["id"] == cand["scenario"]), None)
    if exp_path:
        p = Path(repo_root) / exp_path
        if not p.exists():
            out["expected"].append({"error": f"expected_values file missing: {exp_path}"})
        else:
            spec = json.loads(p.read_text())
            table = cand["tables"].get(spec["table"], {"fields": [], "key": [], "rows": []})
            rows, _ = rows_by_key(table)
            for e in spec["rows"]:
                k = tuple(e["key"])
                tol = tol_for(cfg, spec["table"], spec["field"])
                actual = rows.get(k, {}).get(spec["field"], "<absent>")
                if actual == "<absent>" or not within(e["value"], actual, tol):
                    out["expected"].append({"key": list(k), "expected": e["value"], "actual": actual, "source": e.get("source", "")})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline"); ap.add_argument("--candidate", required=True)
    ap.add_argument("--config", default="regression-check.yml"); ap.add_argument("--json")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config)); repo_root = Path(a.config).resolve().parent
    cdir = Path(a.candidate); bdir = Path(a.baseline) if a.baseline else None
    cfiles = sorted(cdir.glob("*.json"))
    if not cfiles: sys.exit(f"no capture files in {cdir}")
    cands = {json.loads(p.read_text())["scenario"]: json.loads(p.read_text()) for p in cfiles}
    bases = {}
    if bdir:
        for p in sorted(bdir.glob("*.json")):
            d = json.loads(p.read_text()); bases[d["scenario"]] = d

    any_c = next(iter(cands.values()))
    print(f"candidate : {any_c.get('captured_at_commit','?')[:12]} ({any_c.get('label') or any_c.get('branch')})")
    if bases:
        any_b = next(iter(bases.values()))
        print(f"baseline  : {any_b.get('captured_at_commit','?')[:12]} ({any_b.get('label') or any_b.get('branch')})")
    print()

    reports, total = [], 0
    for sid in sorted(set(bases) | set(cands)):
        cand = cands.get(sid)
        rep = {"scenario": sid, "type": (cand or bases[sid]).get("type")}
        if cand is None:
            rep["missing"] = True; total += 1; reports.append(rep)
            print(f"[MISS] {sid}: not captured on candidate"); continue
        if sid in bases:
            rep.update(compare_pair(cfg, bases[sid], cand))
        rep.update(requirement_checks(cfg, cand, repo_root))
        n = sum(len(rep.get(k, [])) for k in ("business", "response", "data", "dependency", "expected"))
        total += n
        print(f"[{'OK  ' if n == 0 else 'FAIL'}] {sid}  ({rep['type']})")
        for d in rep.get("business", []):
            print(f"      business   {('step %d ' % d['step']) if 'step' in d else ''}{d['field']}: {d['baseline']!r} -> {d['candidate']!r}")
        for d in rep.get("response", []):
            print(f"      response   step {d['step']} {d['field']}: {d['baseline']!r} -> {d['candidate']!r}")
        shown = 0
        for d in rep.get("data", []):
            if shown < 6: print(f"      data       {d['table']} key={d['key']} {d['field']}: {d['baseline']!r} -> {d['candidate']!r}")
            shown += 1
        if shown > 6: print(f"      data       ... {shown - 6} more row difference(s)")
        for n_ in rep.get("notes", []): print(f"      summary    {n_}")
        for d in rep.get("dependency", []):
            print(f"      dependency {d['service']} is not an approved dependency ({d['calls']} calls). Approved: {d['approved']}")
        for d in rep.get("expected", []):
            print(f"      expected   {d}")
        reports.append(rep)
    summary = {"scenarios": len(reports), "failed": sum(1 for r in reports if r.get('missing') or any(r.get(k) for k in ('business','response','data','dependency','expected'))),
               "business": sum(len(r.get("business", [])) for r in reports), "response": sum(len(r.get("response", [])) for r in reports),
               "data": sum(len(r.get("data", [])) for r in reports), "dependency": sum(len(r.get("dependency", [])) for r in reports),
               "expected": sum(len(r.get("expected", [])) for r in reports), "missing": [r["scenario"] for r in reports if r.get("missing")]}
    print(); print("summary:", json.dumps(summary))
    if a.json: Path(a.json).write_text(json.dumps({"summary": summary, "scenarios": reports}, indent=2) + "\n")
    sys.exit(1 if total else 0)

if __name__ == "__main__":
    main()
