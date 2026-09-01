#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

UA = "TubeInstanceWatch/0.2 (+https://github.com/yourname/tube-instance-watch)"
TIMEOUT = 15
TEST_VIDEO_ID = "dQw4w9WgXcQ"

DISCOVERY_PATH = Path("data/discovered.json")
STATUS_PATH = Path("data/status.json")
HISTORY_DIR = Path("data/history")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def request(url: str):
    start = time.perf_counter()
    try:
        r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": UA}, allow_redirects=True)
        ms = round((time.perf_counter() - start) * 1000)
        return r, ms, None
    except requests.RequestException as exc:
        return None, None, exc.__class__.__name__


def probe_instance(item: dict) -> dict:
    base = item["api_url"].rstrip("/")

    if item["service"] == "invidious":
        health_url = f"{base}/api/v1/stats"
        playback_url = f"{base}/api/v1/videos/{quote(TEST_VIDEO_ID)}"
    else:
        # Piped API has historically exposed /config and /streams/:videoId.
        # /config gives us a lightweight API health check while /streams tests
        # whether the backend can currently extract a real YouTube video.
        health_url = f"{base}/config"
        playback_url = f"{base}/streams/{quote(TEST_VIDEO_ID)}"

    health_r, latency_ms, health_error = request(health_url)
    health_ok = bool(health_r and 200 <= health_r.status_code < 400)

    playback_ok = False
    playback_status = None
    playback_error = None
    playback_latency_ms = None

    if health_ok:
        play_r, playback_latency_ms, playback_error = request(playback_url)
        playback_status = play_r.status_code if play_r else None
        if play_r and 200 <= play_r.status_code < 400:
            # Avoid a false positive where a proxy returns a generic HTML page.
            ctype = (play_r.headers.get("content-type") or "").lower()
            playback_ok = "json" in ctype or play_r.text.lstrip().startswith(("{", "["))

    return {
        **item,
        "checked_at": now_iso(),
        "health": health_ok,
        "http_status": health_r.status_code if health_r else None,
        "health_error": health_error,
        "latency_ms": latency_ms,
        "playback": playback_ok,
        "playback_status": playback_status,
        "playback_error": playback_error,
        "playback_latency_ms": playback_latency_ms,
        "score": score(health_ok, playback_ok, latency_ms),
    }


def score(health: bool, playback: bool, latency_ms: int | None) -> int:
    value = 0
    if health:
        value += 40
    if playback:
        value += 50
    if latency_ms is not None:
        if latency_ms < 250:
            value += 10
        elif latency_ms < 600:
            value += 7
        elif latency_ms < 1200:
            value += 4
        else:
            value += 1
    return value


def save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    source = json.loads(DISCOVERY_PATH.read_text(encoding="utf-8"))
    results = [probe_instance(item) for item in source["instances"]]
    stamp = now_iso()

    payload = {
        "generated_at": stamp,
        "test_video_id": TEST_VIDEO_ID,
        "instances": results,
    }
    save(STATUS_PATH, payload)

    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    daily = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    history_path = HISTORY_DIR / f"{daily}.jsonl"
    with history_path.open("a", encoding="utf-8") as fh:
        for item in results:
            fh.write(json.dumps({
                "at": stamp,
                "id": item["id"],
                "health": item["health"],
                "playback": item["playback"],
                "latency_ms": item["latency_ms"],
                "score": item["score"],
            }, ensure_ascii=False) + "\n")

    print(f"Checked {len(results)} instances.")


if __name__ == "__main__":
    main()
