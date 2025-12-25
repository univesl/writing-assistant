import argparse
import json
import sys
from typing import List

import httpx


def assert_api_ok(resp: httpx.Response, where: str) -> dict:
    try:
        j = resp.json()
    except Exception:
        raise AssertionError(f"[{where}] not json. status={resp.status_code}, text={resp.text[:200]}")
    if resp.status_code != 200:
        raise AssertionError(f"[{where}] http {resp.status_code}: {j}")
    if j.get("code") != 200:
        raise AssertionError(f"[{where}] api code != 200: {j}")
    return j


def sse_collect_events(client: httpx.Client, url: str, payload: dict, where: str, max_events: int = 20000) -> List[dict]:
    events: List[dict] = []
    with client.stream("POST", url, json=payload, timeout=60.0) as r:
        if r.status_code != 200:
            raise AssertionError(f"[{where}] http {r.status_code}: {r.text[:200]}")
        ctype = r.headers.get("content-type", "")
        if "text/event-stream" not in ctype:
            raise AssertionError(f"[{where}] expected text/event-stream, got {ctype}")

        for line in r.iter_lines():
            if not line:
                continue
            line = line.strip()
            if not line.startswith("data:"):
                continue
            raw = line[len("data:"):].strip()
            evt = json.loads(raw)
            events.append(evt)
            if evt.get("finish") is True:
                break
            if len(events) >= max_events:
                raise AssertionError(f"[{where}] too many events, stream may be stuck.")
    return events


def check_sse(events: List[dict], where: str) -> str:
    if not events:
        raise AssertionError(f"[{where}] no events received")
    if events[-1].get("finish") is not True:
        raise AssertionError(f"[{where}] last event not finish=true")
    final_text = events[-1].get("content", "")
    if not isinstance(final_text, str) or len(final_text) < 5:
        raise AssertionError(f"[{where}] final content invalid: {final_text!r}")
    return final_text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000/api")
    args = ap.parse_args()
    base = args.base_url.rstrip("/")
    print("Base:", base)

    with httpx.Client(base_url=base, timeout=15.0) as client:
        # health
        j = assert_api_ok(client.get("/health"), "health")
        print("✅ health:", j["data"])

        # create session
        j = assert_api_ok(client.post("/session/create", json={"session_name": "自动化测试会话"}), "session/create")
        sid = j["data"]["session_id"]
        print("✅ create session:", sid)

        # list
        j = assert_api_ok(client.get("/session/list"), "session/list")
        if sid not in [x["session_id"] for x in j["data"]]:
            raise AssertionError("session/list missing created session")
        print("✅ list contains session")

        # SSE quick
        ev = sse_collect_events(client, "/write/quick", {"session_id": sid, "prompt": "写一段产品介绍", "model_type": "general"}, "SSE quick")
        quick_text = check_sse(ev, "SSE quick")
        print("✅ SSE quick ok, final len:", len(quick_text))

        # SSE step
        ev = sse_collect_events(
            client,
            "/write/step",
            {
                "session_id": sid,
                "product_name": "测试产品",
                "selling_points": ["轻便", "耐用", "好看"],
                "style": "simple",
                "length": "short"
            },
            "SSE step",
        )
        step_text = check_sse(ev, "SSE step")
        print("✅ SSE step ok, final len:", len(step_text))

        # polish
        j = assert_api_ok(client.post("/write/polish", json={"session_id": sid, "content": "你好  世界", "polish_type": "check"}), "write/polish")
        if "original_content" not in j["data"] or "polished_content" not in j["data"]:
            raise AssertionError("write/polish missing fields")
        print("✅ polish ok")

        # save quick
        j = assert_api_ok(client.post("/write/save", json={"session_id": sid, "content": quick_text, "content_type": "quick"}), "write/save quick")
        cid1 = j["data"]["content_id"]
        print("✅ save quick:", cid1)

        # save step
        j = assert_api_ok(client.post("/write/save", json={"session_id": sid, "content": step_text, "content_type": "step"}), "write/save step")
        cid2 = j["data"]["content_id"]
        print("✅ save step:", cid2)

        # content history
        j = assert_api_ok(client.get(f"/content/get/{sid}"), "content/get")
        got_ids = [x["content_id"] for x in j["data"]]
        if cid1 not in got_ids or cid2 not in got_ids:
            raise AssertionError("content/get missing saved contents")
        print("✅ content history ok, items:", len(j["data"]))

        # rename
        assert_api_ok(client.put(f"/session/rename/{sid}", json={"session_name": "改名后的会话"}), "session/rename")
        print("✅ rename ok")

        # delete
        assert_api_ok(client.delete(f"/session/delete/{sid}"), "session/delete")
        print("✅ delete ok")

        # verify deleted
        j = assert_api_ok(client.get("/session/list"), "session/list after delete")
        if sid in [x["session_id"] for x in j["data"]]:
            raise AssertionError("session still exists after delete")
        print("✅ session removed")

        # content/get should be code=404 in body
        r = client.get(f"/content/get/{sid}")
        jj = r.json()
        if jj.get("code") != 404:
            raise AssertionError(f"expected code=404 after delete, got: {jj}")
        print("✅ content/get after delete returns code=404")

    print("\n🎉 ALL TESTS PASSED.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n❌ TEST FAILED:", str(e))
        sys.exit(1)
