from __future__ import annotations

import os
import time
import uuid
import json
import random
import binascii
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

import requests
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

# -----------------------------
# HARD-CODED CONFIGURATION
# -----------------------------
# Set the target username you want to follow
HARD_CODED_TARGET_USERNAME = "target_username_here"

# Put your TikTok session IDs here
# Example: ["sessionid_value_1", "sessionid_value_2"]
HARD_CODED_SESSIONS: List[str] = [
    "PUT_SESSIONID_1_HERE",
    "PUT_SESSIONID_2_HERE",
]

# UI branding
BANNER_TITLE = "CHYO"
BANNER_HANDLE = "@chyoo_eyes"

# -----------------------------
# STATE
# -----------------------------
state_lock = threading.Lock()
is_running: bool = False
run_logs: List[str] = []
run_total: int = 0
run_done: int = 0
run_start_ts: float | None = None

# -----------------------------
# OPTIONAL DEPENDENCIES (FALLBACKS)
# -----------------------------
# Try to import external modules used by original script. If not available, provide fallbacks
# so the web app can still run and report helpful errors.
try:
    from ms4 import InfoTik  # type: ignore
except Exception:  # pragma: no cover
    class _InfoTikFallback:
        @staticmethod
        def TikTok_Info(username: str) -> Dict[str, Any]:
            # Fallback returns placeholders and instructs to install/provide ms4
            raise RuntimeError(
                "ms4 module not found. Place ms4.py (with InfoTik.TikTok_Info) in the project root."
            )

    InfoTik = _InfoTikFallback()  # type: ignore

try:
    import SignerPy  # type: ignore
except Exception:  # pragma: no cover
    class _SignerPyFallback:
        @staticmethod
        def sign(params: Dict[str, Any], cookie: Dict[str, str]) -> Dict[str, str]:
            # Fallback returns synthetic headers; most likely TikTok will reject, but allows flow for UI demo
            now_ms = str(int(time.time() * 1000))
            return {
                "x-ss-req-ticket": now_ms,
                "x-ss-stub": binascii.hexlify(os.urandom(16)).decode(),
                "x-argus": binascii.hexlify(os.urandom(32)).decode(),
                "x-gorgon": binascii.hexlify(os.urandom(16)).decode(),
                "x-khronos": str(int(time.time())),
                "x-ladon": binascii.hexlify(os.urandom(16)).decode(),
            }

    SignerPy = _SignerPyFallback()  # type: ignore


# -----------------------------
# CORE LOGIC (adapted from main.py)
# -----------------------------

def append_log(message: str) -> None:
    with state_lock:
        run_logs.append(message)
        # Keep only the most recent 500 messages
        if len(run_logs) > 500:
            del run_logs[: len(run_logs) - 500]


def build_follow_params(user_id: str, sec_uid: str) -> Dict[str, Any]:
    model = "Redmi"
    brand = "Xiaomi"
    build = "RP1A.200720.011"

    params: Dict[str, Any] = {
        "user_id": str(user_id),
        "sec_user_id": sec_uid,
        "type": "1",
        "channel_id": "3",
        "from": "19",
        "from_pre": "13",
        "previous_page": "homepage_hot",
        "action_time": str(time.time()).replace(".", "")[:13],
        "is_network_available": "true",
        "device_platform": "android",
        "os": "android",
        "ssmix": "a",
        "_rticket": str(time.time()).replace(".", "")[:13],
        "cdid": str(uuid.uuid4()),
        "channel": "googleplay",
        "aid": "1233",
        "app_name": "musical_ly",
        "version_code": "390603",
        "version_name": "39.6.3",
        "manifest_version_code": "2023906030",
        "update_version_code": "2023906030",
        "ab_version": "39.6.3",
        "resolution": "1080*2220",
        "dpi": "440",
        "app_version": "39.6.3",
        "device_type": model,
        "device_brand": brand,
        "language": "en",
        "os_api": "30",
        "os_version": "11",
        "ac": "mobile",
        "is_pad": "0",
        "current_region": "US",
        "app_type": "normal",
        "sys_region": "US",
        "last_install_time": "1741496448",
        "mcc_mnc": "42103",
        "timezone_name": "Asia/Aden",
        "residence": "US",
        "app_language": "en",
        "carrier_region": "US",
        "timezone_offset": "10800",
        "host_abi": "arm64-v8a",
        "locale": "en",
        "ac2": "lte",
        "uoo": "0",
        "op_region": "US",
        "build_number": "39.6.3",
        "region": "US",
        "ts": str(round(random.uniform(1.2, 1.6) * 100000000) * -1),
        "iid": str(random.randint(1, 10 ** 19)),
        "device_id": str(random.randint(1, 10 ** 19)),
        "openudid": str(binascii.hexlify(os.urandom(8)).decode()),
    }
    return params


def follow_once(session_id: str, user_id: str, sec_uid: str) -> str:
    try:
        params = build_follow_params(user_id=user_id, sec_uid=sec_uid)

        secret = secrets.token_hex(16)
        cookies = {
            "sessionid": session_id,
            "passport_csrf_token": secret,
            "passport_csrf_token_default": secret,
            "tt-target-idc": "useast1a",
            "sid_tt": session_id,
            "store-country-code-src": "uid",
            "store-country-code": "iq",
            "store-idc": "alisg",
        }

        headers = {
            "User-Agent": (
                "com.zhiliaoapp.musically/2023906030 (Linux; U; Android 11; en; "
                "Redmi; Build/RP1A.200720.011; Cronet/TTNetVersion:a482972f)"
            ),
            "x-tt-passport-csrf-token": secret,
            "Cookie": f"sessionid={session_id}",
        }

        signature = SignerPy.sign(params=params, cookie=cookies)  # type: ignore
        headers.update(
            {
                "x-ss-req-ticket": signature["x-ss-req-ticket"],
                "x-ss-stub": signature["x-ss-stub"],
                "x-argus": signature["x-argus"],
                "x-gorgon": signature["x-gorgon"],
                "x-khronos": signature["x-khronos"],
                "x-ladon": signature["x-ladon"],
            }
        )

        url = "https://api16-normal-c-alisg.ttapis.com/aweme/v1/commit/follow/user/"
        response = requests.get(url, params=params, headers=headers, timeout=30)

        if '"status_code":0' in response.text:
            return "success"
        else:
            return f"fail: {response.text[:200]}"  # limit output

    except Exception as ex:  # pragma: no cover
        return f"error: {str(ex)}"


def resolve_tiktok_user(target_username: str) -> Dict[str, str]:
    try:
        user_info = InfoTik.TikTok_Info(target_username)  # type: ignore
        return {"id": str(user_info["id"]), "secuid": str(user_info["secuid"])}
    except Exception as exc:
        raise RuntimeError(
            f"Failed to fetch user info for '{target_username}': {exc}"
        )


def run_follow_flow(sessions: List[str], target_username: str) -> None:
    global is_running, run_total, run_done, run_start_ts

    with state_lock:
        is_running = True
        run_logs.clear()
        run_done = 0
        run_total = len(sessions)
        run_start_ts = time.time()

    append_log(f"Starting follow run for '{target_username}' with {len(sessions)} session(s)...")

    try:
        user = resolve_tiktok_user(target_username)
        user_id = user["id"]
        sec_uid = user["secuid"]
        append_log(f"Resolved user -> id: {user_id}, secuid: {sec_uid}")
    except Exception as e:  # pragma: no cover
        append_log(str(e))
        with state_lock:
            is_running = False
        return

    def _worker(sess: str) -> None:
        nonlocal user_id, sec_uid
        result = follow_once(sess, user_id=user_id, sec_uid=sec_uid)
        with state_lock:
            nonlocal run_done
            run_done += 1
        append_log(f"[{run_done}/{run_total}] {sess[:6]}... -> {result}")

    try:
        with ThreadPoolExecutor(max_workers=min(50, max(1, len(sessions)))) as executor:
            futures = [executor.submit(_worker, s) for s in sessions]
            for _ in as_completed(futures):
                pass
    finally:
        with state_lock:
            is_running = False
        append_log("Run finished.")


# -----------------------------
# ROUTES
# -----------------------------

@app.get("/")
def index():
    return render_template(
        "index.html",
        banner_title=BANNER_TITLE,
        banner_handle=BANNER_HANDLE,
        target_username=HARD_CODED_TARGET_USERNAME,
        session_count=len([s for s in HARD_CODED_SESSIONS if s and not s.startswith("PUT_")]),
    )


@app.post("/start")
def start_run():
    global is_running
    with state_lock:
        if is_running:
            return jsonify({"ok": False, "message": "A run is already in progress."}), 400
        # Validate hard-coded inputs
        sessions = [s.strip() for s in HARD_CODED_SESSIONS if s.strip() and not s.startswith("PUT_")]
        if not sessions:
            return jsonify({"ok": False, "message": "No session IDs are hard-coded. Edit HARD_CODED_SESSIONS in app.py."}), 400
        if not HARD_CODED_TARGET_USERNAME or HARD_CODED_TARGET_USERNAME == "target_username_here":
            return jsonify({"ok": False, "message": "No target username is set. Edit HARD_CODED_TARGET_USERNAME in app.py."}), 400

        # Launch background thread
        t = threading.Thread(
            target=run_follow_flow,
            args=(sessions, HARD_CODED_TARGET_USERNAME),
            daemon=True,
        )
        t.start()
        is_running = True

    return jsonify({"ok": True})


@app.get("/status")
def status():
    with state_lock:
        payload = {
            "running": is_running,
            "done": run_done,
            "total": run_total,
            "startedAt": run_start_ts,
            "logs": run_logs[-150:],  # last 150 messages
            "target": HARD_CODED_TARGET_USERNAME,
            "banner": {
                "title": BANNER_TITLE,
                "handle": BANNER_HANDLE,
            },
        }
    return jsonify(payload)


if __name__ == "__main__":
    # For local dev
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)