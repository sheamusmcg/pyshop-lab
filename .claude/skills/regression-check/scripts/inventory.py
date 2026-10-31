#!/usr/bin/env python3
"""inventory.py - seed the workflow and coverage inventory from code.

    python inventory.py [--config regression-check.yml] [--src pyshop] [--tests tests] [--json out.json]

Finds candidate entry points (Flask routes, argparse commands, calculation
modules), the dependency client classes they reference, conditional branches
on parameters, and which scenarios/tests mention each. Output is a STARTING
POINT: a proposed map for an engineer to confirm. It reads source text, so a
dependency listed here is a lead; proof of use comes from the call log in a
capture. Standard library + PyYAML.
"""
import argparse, json, re, sys
from pathlib import Path
import yaml

ROUTE = re.compile(r'@(\w+)\.(get|post|put|delete|route)\(\s*"([^"]+)"')
ARG = re.compile(r'add_argument\(\s*"(--[\w-]+)"')
CLASS_USE = re.compile(r'\b(Pricing\w+|\w+Client|\w+Service)\(')
BRANCH = re.compile(r'^\s*(if|elif)\s+(.+?):\s*$', re.M)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="regression-check.yml"); ap.add_argument("--src", default=None)
    ap.add_argument("--tests", default="tests"); ap.add_argument("--json")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config)) if Path(a.config).exists() else {}
    approved = set(cfg.get("approved_dependencies") or []); deprecated = set(cfg.get("deprecated_dependencies") or [])
    src = Path(a.src) if a.src else Path(cfg.get("project", ".")) if Path(cfg.get("project", ".")).exists() else Path(".")
    scen_text = json.dumps(cfg.get("scenarios", []))
    test_text = "\n".join(p.read_text(errors="ignore") for p in Path(a.tests).rglob("*.py")) if Path(a.tests).exists() else ""
    # map service class -> declared name, e.g. class PricingLegacy: name = "pricing-legacy"
    names = {}
    for p in src.rglob("*.py"):
        t = p.read_text(errors="ignore")
        for m in re.finditer(r'class (\w+)\([^)]*\):(?:.|\n)*?name = "([^"]+)"', t): names[m.group(1)] = m.group(2)
    entries = []
    for p in sorted(src.rglob("*.py")):
        t = p.read_text(errors="ignore"); rel = str(p)
        eps = [f"{m.group(2).upper()} {m.group(3)}" for m in ROUTE.finditer(t)]
        args = ARG.findall(t)
        if not eps and not args and "def run" not in t: continue
        deps = sorted({names.get(c, c) for c in CLASS_USE.findall(t)})
        branches = [b.strip() for b in BRANCH.findall(t) for b in [b[1]] if any(k in b for k in ("region", "scenario", "flag", "type", "has_", "param", "args.", "==", "in ("))][:8]
        status = {d: ("deprecated" if d in deprecated else "approved" if d in approved else "unknown") for d in deps}
        covered_by = []
        for key in eps + [rel.split("/")[-1].replace(".py", "")]:
            if key.split(" ")[-1] in scen_text: covered_by.append(f"scenario mentions {key}")
            if key.split(" ")[-1] in test_text: covered_by.append(f"test mentions {key}")
        entries.append({"file": rel, "entry_points": eps, "parameters": args, "dependencies": status,
                        "conditional_branches": branches, "covered_by": sorted(set(covered_by)),
                        "flags": ([f"calls deprecated dependency: {d}" for d, s in status.items() if s == "deprecated"]
                                  + ([] if covered_by else ["no scenario or test mentions this entry point"]))})
    print("# Workflow and coverage inventory (proposed; confirm against the code and a capture)\n")
    for e in entries:
        print(f"## {e['file']}")
        if e["entry_points"]: print(f"- entry points: {', '.join(e['entry_points'])}")
        if e["parameters"]: print(f"- parameters: {', '.join(e['parameters'])}")
        if e["dependencies"]: print(f"- dependencies: " + ", ".join(f"{d} ({s})" for d, s in e["dependencies"].items()))
        if e["conditional_branches"]: print(f"- conditional branches: " + " | ".join(e["conditional_branches"]))
        print(f"- covered by: {', '.join(e['covered_by']) or 'nothing found'}")
        for f in e["flags"]: print(f"- FLAG: {f}")
        print()
    if a.json: Path(a.json).write_text(json.dumps(entries, indent=2))

if __name__ == "__main__":
    main()
