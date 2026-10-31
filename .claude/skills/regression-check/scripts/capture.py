#!/usr/bin/env python3
"""capture.py - run the configured scenarios against fresh, controlled state and
record what each produced: responses, stdout summaries, persisted rows and the
outbound service calls it made.

    python capture.py [--config regression-check.yml] [--out DIR] [--label L]
                      [--scenario ID ...] [--repo-root PATH] [--type batch|service|calculation|ui]

Scenario types
  batch        run a command; parse its stdout; snapshot tables; record calls
  calculation  run a command; snapshot result_table; record calls
  service      start the app; run request / cache / clock steps; snapshot; record calls
  ui           like service, plus browser steps (Playwright) that read page values

Every scenario: fresh database (seeded on first app/command start), optional
setup commands, then the steps. The call_log table is read after the scenario
and written to the capture, so a later check can prove which dependency ran.

Standard library + PyYAML. Playwright only for ui scenarios.
Exit: 0 captured; 2 config/setup error; 3 app failed to start.
"""
import argparse, json, os, re, shlex, shutil, socket, sqlite3, subprocess, sys, tempfile, time
import urllib.request, urllib.error
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("capture.py needs PyYAML: pip install pyyaml")


# ----------------------------------------------------------------------------- utils
def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)

def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]

def wait_ready(url, timeout_s):
    end = time.time() + timeout_s
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=2).read(); return True
        except Exception:
            time.sleep(0.25)
    return False

def http(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data else {})
    try:
        r = urllib.request.urlopen(req, timeout=30); status, raw, hdr = r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        status, raw, hdr = e.code, e.read(), dict(e.headers)
    try:
        parsed = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        parsed = raw.decode(errors="replace")
    return {"status": status, "headers": hdr, "body": parsed}

def _set_path(obj, parts, value):
    if not parts: return value
    head, rest = parts[0], parts[1:]
    if head == "*":
        if isinstance(obj, dict): return {k: _set_path(v, rest, value) for k, v in obj.items()}
        if isinstance(obj, list): return [_set_path(v, rest, value) for v in obj]
        return obj
    if isinstance(obj, list) and head.isdigit():
        i = int(head)
        if i < len(obj): obj = list(obj); obj[i] = _set_path(obj[i], rest, value)
        return obj
    if isinstance(obj, dict) and head in obj:
        obj = dict(obj); obj[head] = _set_path(obj[head], rest, value)
    return obj

def split_path(p):
    p = p[2:] if p.startswith("$.") else p
    return [x for x in re.split(r"\.|\[|\]", p) if x]

def normalize(record, rules):
    for rule in rules or []:
        record = _set_path(record, split_path(rule["path"]), rule.get("replace", "<normalized>"))
    return record

def snapshot_tables(db_path, tables):
    out = {}
    con = sqlite3.connect(db_path)
    try:
        for t in tables:
            where = f" WHERE {t['where']}" if t.get("where") else ""
            rows = con.execute(f"SELECT {', '.join(t['fields'])} FROM {t['name']}{where} "
                               f"ORDER BY {', '.join(t['key'])}").fetchall()
            out[t["name"]] = {"fields": t["fields"], "key": t["key"], "rows": [list(r) for r in rows]}
    finally:
        con.close()
    return out

def read_call_log(db_path, table):
    if not table: return []
    con = sqlite3.connect(db_path)
    try:
        try:
            rows = con.execute(f"SELECT service, operation, detail FROM {table} ORDER BY id").fetchall()
        except sqlite3.OperationalError:
            return []
    finally:
        con.close()
    return [{"service": s, "operation": o, "detail": d} for s, o, d in rows]

def call_summary(calls):
    out = {}
    for c in calls: out[c["service"]] = out.get(c["service"], 0) + 1
    return dict(sorted(out.items()))

def env_for(cfg, db_path, port=None):
    env = dict(os.environ)
    for k, v in (cfg.get("app", {}).get("env") or {}).items():
        env[k] = v.format(db=db_path, port=port or 0)
    return env

def run_cmd(cmd, cwd, env, log_path):
    with open(log_path, "a") as log:
        log.write(f"$ {cmd}\n")
        p = subprocess.run(cmd, shell=True, cwd=cwd, env=env, capture_output=True, text=True)
        log.write(p.stdout); log.write(p.stderr)
    return p


# ----------------------------------------------------------------------------- app lifecycle
class App:
    def __init__(self, cfg, repo_root, db_path, log_path):
        self.cfg, self.repo_root, self.db_path, self.log_path = cfg, repo_root, db_path, log_path
        self.port = free_port(); self.proc = None
        self.base = f"http://127.0.0.1:{self.port}"

    def __enter__(self):
        cmd = self.cfg["app"]["start"].format(db=self.db_path, port=self.port)
        self.log = open(self.log_path, "a"); self.log.write(f"$ {cmd}\n"); self.log.flush()
        # Own process group, so shutdown reaches the server even when the shell
        # wrapper exits first, and an interrupted capture leaves no orphans.
        self.proc = subprocess.Popen(cmd, shell=True, cwd=self.repo_root, stdout=self.log, stderr=subprocess.STDOUT,
                                     env={**env_for(self.cfg, self.db_path, self.port), "PYTHONUNBUFFERED": "1"},
                                     start_new_session=True)
        if not wait_ready(self.cfg["app"]["ready_url"].format(port=self.port), self.cfg["app"].get("ready_timeout_s", 20)):
            self.__exit__(None, None, None)
            sys.stderr.write(f"app did not become ready; see {self.log_path}\n"); sys.exit(3)
        return self

    def __exit__(self, *a):
        if self.proc:
            import signal
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(os.getpgid(self.proc.pid), sig)
                    self.proc.wait(timeout=5); break
                except ProcessLookupError:
                    break
                except subprocess.TimeoutExpired:
                    continue
        self.log.close()


# ----------------------------------------------------------------------------- scenario handlers
def do_setup(cfg, sc, repo_root, db_path, log_path):
    for cmd in sc.get("setup") or []:
        p = run_cmd(cmd, repo_root, env_for(cfg, db_path), log_path)
        if p.returncode != 0:
            sys.stderr.write(f"[{sc['id']}] setup failed: {cmd}\n{p.stderr}\n"); sys.exit(2)

def run_command_scenario(cfg, sc, repo_root, db_path, log_path):
    p = run_cmd(sc["command"], repo_root, env_for(cfg, db_path), log_path)
    summary = {}
    if sc.get("parse_stdout"):
        m = re.search(sc["parse_stdout"], p.stdout)
        if m: summary = {k: (int(v) if v.isdigit() else v) for k, v in m.groupdict().items()}
    return {"command": sc["command"], "exit_code": p.returncode,
            "stdout_tail": p.stdout.strip().splitlines()[-3:], "summary": summary}

def run_service_steps(cfg, sc, app, repo_root, log_path):
    steps_out = []
    pw = browser = page = None
    for i, step in enumerate(sc["steps"]):
        rec = {"index": i, "business_fields": step.get("business_fields", [])}
        if "request" in step:
            r = step["request"]
            rec.update({"kind": "request", "method": r["method"], "path": r["path"], "request": r.get("json")})
            rec.update(normalize({"response": http(r["method"], app.base + r["path"], r.get("json"))}, cfg.get("normalize")))
        elif "clock" in step:
            adv = step["clock"].get("advance_seconds", 0)
            rec.update({"kind": "clock", "advance_seconds": adv,
                        "response": http("POST", app.base + "/clock/advance", {"seconds": adv})})
        elif "fixture" in step:
            # Change controlled state mid-scenario (e.g. the source data after it was cached,
            # or a fault switch). A shell command run with the scenario's database in env.
            p = run_cmd(step["fixture"], repo_root, env_for(cfg, app.db_path, app.port), log_path)
            rec.update({"kind": "fixture", "command": step["fixture"],
                        "response": {"status": p.returncode, "body": p.stdout.strip().splitlines()[-1:] or None}})
        elif "cache" in step:
            rec.update({"kind": "cache", "action": step["cache"]})
            rec["response"] = http("GET", app.base + "/cache/stats")
        elif "browser" in step:
            if pw is None:
                try:
                    from playwright.sync_api import sync_playwright
                except ImportError:
                    sys.exit("ui scenarios need Playwright: pip install playwright && playwright install chromium")
                pw = sync_playwright().start(); browser = pw.chromium.launch(); page = browser.new_page()
            b = step["browser"]
            page.goto(app.base + b["goto"]); page.wait_for_load_state("networkidle")
            value = page.locator(b["read"]["selector"]).first.inner_text().strip()
            rec.update({"kind": "browser", "goto": b["goto"], "selector": b["read"]["selector"],
                        "response": {"status": 200, "body": {b["read"].get("as", "value"): value}}})
        steps_out.append(rec)
    if browser: browser.close(); pw.stop()
    return steps_out

def run_scenario(cfg, sc, repo_root, workdir):
    db_path = os.path.join(workdir, f"{sc['id']}.db")
    log_path = os.path.join(workdir, f"{sc['id']}.log")
    if os.path.exists(db_path): os.remove(db_path)
    result = {"scenario": sc["id"], "type": sc.get("type", "service"), "description": sc.get("description", ""),
              "expect_dependencies": sc.get("expect_dependencies"), "business_fields": sc.get("business_fields", [])}
    kind = result["type"]
    if kind in ("batch", "calculation"):
        # seed the fresh DB the same way the app would, so command scenarios start from the seed
        with App(cfg, repo_root, db_path, log_path):
            pass
        do_setup(cfg, sc, repo_root, db_path, log_path)
        result["run"] = run_command_scenario(cfg, sc, repo_root, db_path, log_path)
        if kind == "calculation":
            result["result_table"] = sc.get("result_table")
    else:
        with App(cfg, repo_root, db_path, log_path) as app:
            do_setup(cfg, sc, repo_root, db_path, log_path)
            result["steps"] = run_service_steps(cfg, sc, app, repo_root, log_path)
    result["tables"] = snapshot_tables(db_path, cfg["database"]["tables"])
    calls = read_call_log(db_path, cfg["database"].get("call_log_table"))
    result["calls"] = {"by_service": call_summary(calls), "count": len(calls), "sample": calls[:5]}
    return result


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="regression-check.yml")
    ap.add_argument("--out"); ap.add_argument("--label"); ap.add_argument("--repo-root")
    ap.add_argument("--scenario", action="append"); ap.add_argument("--type", action="append")
    a = ap.parse_args()
    cfg_path = Path(a.config).resolve(); cfg = load_config(cfg_path)
    repo_root = Path(a.repo_root).resolve() if a.repo_root else cfg_path.parent
    out_dir = Path(a.out) if a.out else repo_root / cfg["baseline_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    commit = git("rev-parse", "HEAD", cwd=repo_root)
    dirty = bool(git("status", "--porcelain", "--untracked-files=no", cwd=repo_root))
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo_root)
    scs = [s for s in cfg["scenarios"] if (not a.scenario or s["id"] in a.scenario) and (not a.type or s.get("type") in a.type)]
    if not scs: sys.exit("no scenarios matched")
    workdir = tempfile.mkdtemp(prefix="regression-check-")
    for sc in scs:
        res = run_scenario(cfg, sc, repo_root, workdir)
        res = {"captured_at_commit": commit, "branch": branch, "dirty_worktree": dirty, "label": a.label,
               "project": cfg.get("project"), **res}
        (out_dir / f"{sc['id']}.json").write_text(json.dumps(res, indent=2) + "\n")
        rows = sum(len(t["rows"]) for t in res["tables"].values())
        print(f"captured {sc['id']:<32} [{res['type']:<11}] rows={rows:<5} calls={res['calls']['by_service']}")
    shutil.rmtree(workdir, ignore_errors=True)
    print(f"commit {commit[:12]}{' (dirty)' if dirty else ''} on {branch}; {len(scs)} scenario(s) -> {out_dir}")

if __name__ == "__main__":
    main()
