import urllib.request, json, sys

BASE = "http://127.0.0.1:8080"

def get(path):
    try:
        r = urllib.request.urlopen(f"{BASE}{path}", timeout=10)
        return r.status, json.loads(r.read())
    except Exception as e:
        return 500, str(e)

def post(path, data):
    try:
        req = urllib.request.Request(f"{BASE}{path}", data=json.dumps(data).encode(),
                                     headers={"Content-Type": "application/json"})
        r = urllib.request.urlopen(req, timeout=10)
        return r.status, json.loads(r.read())
    except Exception as e:
        return 500, str(e)

ok = 0
fail = 0

def check(name, status, result, expect_ok=True):
    global ok, fail
    if expect_ok and status != 200:
        print(f"  FAIL {name}: HTTP {status} - {result}")
        fail += 1
    elif not expect_ok and status == 200:
        print(f"  FAIL {name}: expected error but got HTTP {status}")
        fail += 1
    else:
        print(f"  OK   {name}: HTTP {status}")
        ok += 1

print("=== Memory endpoints ===")
s, r = get("/api/memory/list")
check("/api/memory/list", s, r)
s, r = get("/api/memory/search?q=test")
check("/api/memory/search", s, r)
s, r = get("/api/memory/path")
check("/api/memory/path", s, r)

print("\n=== Task queue ===")
s, r = get("/api/tasks")
check("GET /api/tasks", s, r)
s, r = post("/api/tasks", {"description": "test", "prompt": "say hi"})
check("POST /api/tasks", s, r)
if s == 200 and isinstance(r, dict):
    tid = r.get("id", "")
    print(f"  Created task: {tid}")
    s, r = post(f"/api/tasks/{tid}/cancel", {})
    check(f"POST /api/tasks/{tid}/cancel", s, r)

print("\n=== Tools list ===")
s, r = get("/api/tools")
check("GET /api/tools", s, r)
if s == 200:
    names = sorted([t["name"] for t in r if isinstance(t, dict)])
    new_tools = [n for n in names if n in ("glob_search", "read", "webfetch", "task", "diagnostics", "sourcegraph", "web_fetch")]
    print(f"  New tools registered: {new_tools}")
    missing = [n for n in ("glob_search", "read", "webfetch", "task", "diagnostics", "sourcegraph") if n not in names]
    if missing:
        print(f"  MISSING tools: {missing}")
        fail += len(missing)
    else:
        print(f"  All new tools present!")
        ok += 1

print(f"\n=== Summary: {ok} passed, {fail} failed ===")
sys.exit(fail)
