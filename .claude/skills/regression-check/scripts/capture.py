#!/usr/bin/env python3
"""capture.py - run the configured scenarios against a fresh database and record
responses + persisted data as baseline JSON files.

    python capture.py --config regression-check.yml --out tests/baselines [--label main]
    python capture.py ... --scenario order_two_mugs      # one scenario only

Each scenario gets its own fresh database and its own app process. Output per
scenario: <out>/<scenario_id>.json with the commit hash, the normalized step
responses, and the declared table rows after the last step.

Standard library only. Requires: git, the project's own run command.
Exit codes: 0 captured; 2 config/setup error; 3 app failed to start.
"""
import argparse, json, os, re, shutil, socket, sqlite3, subprocess, sys, tempfile, time, urllib.request, urllib.error
from pathlib import Path

try:
    import yaml  # PyYAML is a project dependency on both tracks (via requirements / tooling)
except ImportError:
    sys.exit("capture.py needs PyYAML: pip install pyyaml")


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_ready(url, timeout_s):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2).read()
            return True
        except Exception:
            time.sleep(0.25)
    return False


def http(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data else {})
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        status, raw, headers = resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        status, raw, headers = e.code, e.read(), dict(e.headers)
    try:
        parsed = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        parsed = raw.decode(errors="replace")
    return {"status": status, "headers": headers, "body": parsed}


# --- JSON-path normalization: supports $.a.b, $.a[0].b, and a trailing wildcard $.a.* ---
def _walk_set(obj, parts, value):
    if not parts:
        return value
    head, rest = parts[0], parts[1:]
    if head == "*":
        if isinstance(obj, dict):
            return {k: _walk_set(v, rest, value) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_walk_set(v, rest, value) for v in obj]
        return obj
    if isinstance(obj, list) and head.isdigit():
        i = int(head)
        if i < len(obj):
            obj = list(obj); obj[i] = _walk_set(obj[i], rest, value)
        return obj
    if isinstance(obj, dict) and head in obj:
        obj = dict(obj); obj[head] = _walk_set(obj[head], rest, value)
    return obj


def split_path(p):
    p = p[2:] if p.startswith("$.") else p
    return [x for x in re.split(r"\.|\[|\]", p) if x]


def normalize(record, rules):
    for rule in rules or []:
        record = _walk_set(record, split_path(rule["path"]), rule.get("replace", "<normalized>"))
    return record


def snapshot_tables(db_path, tables):
    out = {}
    con = sqlite3.connect(db_path)
    try:
        for t in tables:
            cols = ", ".join(t["fields"])
            order = ", ".join(t["key"])
            where = f" WHERE {t['where']}" if t.get("where") else ""
            rows = con.execute(f"SELECT {cols} FROM {t['name']}{where} ORDER BY {order}").fetchall()
            out[t["name"]] = {"fields": t["fields"], "key": t["key"],
                              "rows": [list(r) for r in rows]}
    finally:
        con.close()
    return out


def run_scenario(cfg, scenario, repo_root, workdir):
    db_path = os.path.join(workdir, f"{scenario['id']}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    port = free_port()
    cmd = cfg["app"]["start"].format(db=db_path, port=port)
    log = open(os.path.join(workdir, f"{scenario['id']}.app.log"), "w")
    proc = subprocess.Popen(cmd, shell=True, cwd=repo_root, stdout=log, stderr=subprocess.STDOUT,
                            env={**os.environ, "PYTHONUNBUFFERED": "1"})
    try:
        ready = cfg["app"]["ready_url"].format(port=port)
        if not wait_ready(ready, cfg["app"].get("ready_timeout_s", 20)):
            proc.kill(); log.close()
            sys.stderr.write(f"[{scenario['id']}] app did not become ready; see {log.name}\n")
            sys.exit(3)
        base = ready.rsplit("/", 1)[0] if ready.endswith("/") else ready
        base = f"http://127.0.0.1:{port}"
        steps_out = []
        for i, step in enumerate(scenario["steps"]):
            resp = http(step["method"], base + step["path"], step.get("json"))
            rec = normalize({"response": resp}, cfg.get("normalize"))
            steps_out.append({"index": i, "method": step["method"], "path": step["path"],
                              "request": step.get("json"),
                              "business_fields": step.get("business_fields", []),
                              **rec})
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()
    tables = snapshot_tables(db_path, cfg["database"]["tables"])
    return {"scenario": scenario["id"], "description": scenario.get("description", ""),
            "steps": steps_out, "tables": tables}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="regression-check.yml")
    ap.add_argument("--out", help="output directory (default: baseline_dir from config)")
    ap.add_argument("--label", default=None, help="free-text label stored in each file, e.g. main or pr-42")
    ap.add_argument("--scenario", action="append", help="limit to these scenario ids")
    ap.add_argument("--repo-root", default=None, help="checkout to run (default: config's directory)")
    args = ap.parse_args()

    cfg_path = Path(args.config).resolve()
    cfg = load_config(cfg_path)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else cfg_path.parent
    out_dir = Path(args.out) if args.out else repo_root / cfg["baseline_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    commit = git("rev-parse", "HEAD", cwd=repo_root)
    dirty = bool(git("status", "--porcelain", "--untracked-files=no", cwd=repo_root))
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo_root)

    wanted = set(args.scenario or [])
    scenarios = [s for s in cfg["scenarios"] if not wanted or s["id"] in wanted]
    if not scenarios:
        sys.exit(f"no scenarios matched {sorted(wanted)}")

    workdir = tempfile.mkdtemp(prefix="regression-check-")
    written = []
    for sc in scenarios:
        result = run_scenario(cfg, sc, repo_root, workdir)
        result = {"captured_at_commit": commit, "branch": branch, "dirty_worktree": dirty,
                  "label": args.label, "project": cfg.get("project"), **result}
        path = out_dir / f"{sc['id']}.json"
        path.write_text(json.dumps(result, indent=2, sort_keys=False) + "\n")
        written.append(str(path))
        print(f"captured {sc['id']}: {len(result['steps'])} steps, "
              f"{sum(len(t['rows']) for t in result['tables'].values())} rows -> {path}")
    shutil.rmtree(workdir, ignore_errors=True)
    print(f"commit {commit[:12]}{' (dirty)' if dirty else ''} on {branch}; {len(written)} file(s)")


if __name__ == "__main__":
    main()
