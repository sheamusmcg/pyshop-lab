#!/usr/bin/env python3
"""compare.py - deterministic, field-level comparison of two capture directories.

    python compare.py --baseline tests/baselines --candidate /tmp/candidate [--json report.json]

For every scenario present in the baseline: compares each step's status and
body field by field, and each declared table row by its key. Reports:
  - business-field differences (the fields the config named)
  - other response differences
  - persisted-data differences: changed rows, rows only in one side
  - scenarios missing from the candidate
Normalization was applied at capture time, so this script compares literally.

Exit codes: 0 no differences; 1 differences found; 2 input error.
It never edits a baseline. Updating a baseline is a reviewed change (see SKILL.md).
"""
import argparse, json, sys
from pathlib import Path


def flatten(obj, prefix=""):
    """{'a':{'b':1},'c':[2,3]} -> {'a.b':1,'c[0]':2,'c[1]':3}"""
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = obj
    return out


def diff_flat(a, b):
    keys = sorted(set(a) | set(b))
    return [{"field": k, "baseline": a.get(k, "<absent>"), "candidate": b.get(k, "<absent>")}
            for k in keys if a.get(k, "<absent>") != b.get(k, "<absent>")]


def rows_by_key(table):
    idx = [table["fields"].index(k) for k in table["key"]]
    return {tuple(r[i] for i in idx): dict(zip(table["fields"], r)) for r in table["rows"]}


def compare_scenario(base, cand):
    report = {"scenario": base["scenario"], "business": [], "response": [], "data": [], "notes": []}
    if base.get("captured_at_commit") == cand.get("captured_at_commit"):
        report["notes"].append("same commit on both sides")
    for i, bstep in enumerate(base["steps"]):
        if i >= len(cand["steps"]):
            report["response"].append({"step": i, "field": "<step>", "baseline": "present", "candidate": "<absent>"})
            continue
        cstep = cand["steps"][i]
        bflat = flatten({"status": bstep["response"]["status"], **({"body": bstep["response"]["body"]} if bstep["response"]["body"] is not None else {})})
        cflat = flatten({"status": cstep["response"]["status"], **({"body": cstep["response"]["body"]} if cstep["response"]["body"] is not None else {})})
        business = set(f"body.{f}" for f in bstep.get("business_fields", []))
        for d in diff_flat(bflat, cflat):
            d["step"] = i
            (report["business"] if d["field"] in business or d["field"] == "status" else report["response"]).append(d)
        # business fields may name a whole subtree (e.g. "lines"); match by prefix
        for d in list(report["response"]):
            if any(d["field"].startswith(f"body.{f}[") or d["field"].startswith(f"body.{f}.") for f in bstep.get("business_fields", [])):
                report["response"].remove(d); report["business"].append(d)
    for tname, btable in base["tables"].items():
        ctable = cand["tables"].get(tname)
        if ctable is None:
            report["data"].append({"table": tname, "key": "*", "field": "<table>", "baseline": "present", "candidate": "<absent>"})
            continue
        brows, crows = rows_by_key(btable), rows_by_key(ctable)
        for key in sorted(set(brows) | set(crows), key=str):
            if key not in crows:
                report["data"].append({"table": tname, "key": list(key), "field": "<row>", "baseline": brows[key], "candidate": "<absent>"})
            elif key not in brows:
                report["data"].append({"table": tname, "key": list(key), "field": "<row>", "baseline": "<absent>", "candidate": crows[key]})
            else:
                for f in btable["fields"]:
                    if brows[key].get(f) != crows[key].get(f):
                        report["data"].append({"table": tname, "key": list(key), "field": f,
                                               "baseline": brows[key].get(f), "candidate": crows[key].get(f)})
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--json", help="also write the full report here")
    args = ap.parse_args()
    bdir, cdir = Path(args.baseline), Path(args.candidate)
    if not bdir.is_dir() or not cdir.is_dir():
        sys.exit("baseline and candidate must be directories of capture JSON files")

    reports, missing = [], []
    bfiles = sorted(bdir.glob("*.json"))
    if not bfiles:
        sys.exit(f"no baseline files in {bdir}")
    for bf in bfiles:
        cf = cdir / bf.name
        base = json.loads(bf.read_text())
        if not cf.exists():
            missing.append(base["scenario"]); continue
        reports.append(compare_scenario(base, json.loads(cf.read_text())))

    first_b = json.loads(bfiles[0].read_text())
    cfirst = next((json.loads(p.read_text()) for p in sorted(cdir.glob("*.json"))), {})
    print(f"baseline  : {first_b.get('captured_at_commit','?')[:12]} ({first_b.get('label') or first_b.get('branch')})")
    print(f"candidate : {cfirst.get('captured_at_commit','?')[:12]} ({cfirst.get('label') or cfirst.get('branch')})")
    print()

    total = 0
    for r in reports:
        n = len(r["business"]) + len(r["response"]) + len(r["data"])
        total += n
        mark = "OK  " if n == 0 else "DIFF"
        print(f"[{mark}] {r['scenario']}")
        for d in r["business"]:
            print(f"      business  step {d['step']} {d['field']}: {d['baseline']!r} -> {d['candidate']!r}")
        for d in r["response"]:
            print(f"      response  step {d['step']} {d['field']}: {d['baseline']!r} -> {d['candidate']!r}")
        for d in r["data"]:
            print(f"      data      {d['table']} key={d['key']} {d['field']}: {d['baseline']!r} -> {d['candidate']!r}")
    for m in missing:
        print(f"[MISS] {m}: not captured on candidate")
    print()
    summary = {"scenarios": len(reports), "with_differences": sum(1 for r in reports if r["business"] or r["response"] or r["data"]),
               "business_field_differences": sum(len(r["business"]) for r in reports),
               "other_response_differences": sum(len(r["response"]) for r in reports),
               "persisted_data_differences": sum(len(r["data"]) for r in reports),
               "missing_on_candidate": missing}
    print("summary:", json.dumps(summary))
    if args.json:
        Path(args.json).write_text(json.dumps({"summary": summary, "scenarios": reports}, indent=2) + "\n")
    sys.exit(1 if total or missing else 0)


if __name__ == "__main__":
    main()
