#!/usr/bin/env python3
import os, json, urllib.request
tok = os.environ["GH_TOKEN"]
def get(path):
    req = urllib.request.Request("https://api.github.com" + path,
        headers={"Authorization": "Bearer " + tok, "User-Agent": "arewaos-agent",
                 "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"_status": e.code, "_body": e.read().decode()[:200]}

repo = "0xzahra/seykota-contributions"
print("=== repo ===", get("/repos/" + repo).get("full_name"))
# top-level tree (recursive so we know the whole layout for collision check)
t = get("/repos/" + repo + "/git/trees/HEAD?recursive=1")
if "_status" in t:
    print("tree resp:", t); raise SystemExit(1)
paths = [e["path"] for e in t.get("tree", [])]
print("file count:", len(paths))
coll = [p for p in paths if p.lower().startswith("agent-launchpad")]
print("agent-launchpad collision?", coll if coll else "none — safe to add new dir")
# show top-level dirs
tops = sorted({p.split("/")[0] for p in paths})
print("existing top-level:", tops)
