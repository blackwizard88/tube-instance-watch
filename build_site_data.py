#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REGISTRY = Path("data/registry.json")
STATUS = Path("data/status.json")
EVENTS = Path("data/events.json")
HISTORY = Path("data/history")
OUT = Path("data/instances.json")


def load(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def parse_iso(v):
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except Exception:
        return None


def read_history(days=30):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = defaultdict(list)
    for path in sorted(HISTORY.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            at = parse_iso(item.get("at", ""))
            if at and at >= cutoff:
                rows[item["id"]].append(item)
    return rows


def uptime(samples, days):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    relevant = [s for s in samples if (parse_iso(s.get("at", "")) or cutoff) >= cutoff]
    if not relevant:
        return None
    good = sum(1 for s in relevant if s.get("health") and s.get("playback"))
    return round(good * 100 / len(relevant), 1)


def main():
    reg = load(REGISTRY, {"instances": {}})
    status = load(STATUS, {"instances": [], "generated_at": None})
    events = load(EVENTS, {"events": []})
    history = read_history()

    latest = {x["id"]: x for x in status.get("instances", [])}
    out = []
    for iid, meta in reg.get("instances", {}).items():
        if not meta.get("listed"):
            continue
        merged = {**meta, **latest.get(iid, {})}
        samples = history.get(iid, [])
        merged["uptime_24h"] = uptime(samples, 1)
        merged["uptime_7d"] = uptime(samples, 7)
        merged["uptime_30d"] = uptime(samples, 30)
        out.append(merged)

    recent_events = list(reversed(events.get("events", [])[-100:]))

    payload = {
        "generated_at": status.get("generated_at"),
        "instances": out,
        "recent_events": recent_events,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Built site data for {len(out)} instances.")


if __name__ == "__main__":
    main()
