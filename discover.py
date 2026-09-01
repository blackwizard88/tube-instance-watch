#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

UA = "TubeInstanceWatch/0.2 (+https://github.com/yourname/tube-instance-watch)"
TIMEOUT = 15

INVIDIOUS_DOC = "https://docs.invidious.io/instances/"
PIPED_RAW = "https://raw.githubusercontent.com/TeamPiped/documentation/main/content/docs/public-instances/index.md"

STATE_PATH = Path("data/registry.json")
DISCOVERY_PATH = Path("data/discovered.json")
EVENTS_PATH = Path("data/events.json")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get(url: str) -> requests.Response:
    r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": UA})
    r.raise_for_status()
    return r


def host_from_url(url: str) -> str:
    return urlparse(url).hostname or url


def discover_invidious() -> list[dict]:
    """
    Source: official Invidious public-instance documentation.
    We parse only the bullet list under the public instance heading and ignore
    source-code links that occur later in each bullet.
    """
    html = get(INVIDIOUS_DOC).text
    soup = BeautifulSoup(html, "html.parser")

    heading = None
    for h in soup.find_all(["h2", "h3"]):
        if "List of public Invidious Instances" in h.get_text(" ", strip=True):
            heading = h
            break
    if heading is None:
        raise RuntimeError("Could not find the Invidious public-instance section")

    out = []
    node = heading.find_next_sibling()
    while node and node.name not in ("h2", "h3"):
        if node.name == "ul":
            for li in node.find_all("li", recursive=False):
                first_link = li.find("a", href=True)
                if not first_link:
                    continue
                url = first_link["href"].strip().rstrip("/")
                if not url.startswith("https://"):
                    continue
                host = host_from_url(url)
                text = li.get_text(" ", strip=True)
                flags = "".join(re.findall(r"[\U0001F1E6-\U0001F1FF]{2}", text))
                out.append({
                    "id": f"invidious:{host}",
                    "service": "invidious",
                    "name": host,
                    "url": url,
                    "api_url": url,
                    "location": flags,
                    "cdn": None,
                    "source": INVIDIOUS_DOC,
                })
        node = node.find_next_sibling()

    if not out:
        raise RuntimeError("No Invidious instances discovered")
    return out


def strip_md_link(value: str) -> tuple[str, str | None]:
    value = value.strip()
    m = re.search(r"\[([^\]]+)\]\((https?://[^)]+)\)", value)
    if m:
        return m.group(1).strip(), m.group(2).strip().rstrip("/")
    raw = re.search(r"https?://[^\s|)]+", value)
    return re.sub(r"[*_`]", "", value).strip(), raw.group(0).rstrip("/") if raw else None


def discover_piped() -> list[dict]:
    """
    Source: TeamPiped's current public-instance markdown table.
    The table exposes Instance Name, API URL, locations and CDN.
    """
    text = get(PIPED_RAW).text
    lines = [line.strip() for line in text.splitlines()]
    header_index = next(
        (i for i, line in enumerate(lines)
         if "Instance Name" in line and "Instance API URL" in line),
        None
    )
    if header_index is None:
        raise RuntimeError("Could not find the Piped public-instance table")

    out = []
    for line in lines[header_index + 2:]:
        if not line.startswith("|") and "|" not in line:
            if out:
                break
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) < 4:
            continue

        display_name, frontend = strip_md_link(parts[0])
        _, api_url = strip_md_link(parts[1])
        if not api_url:
            continue

        api_host = host_from_url(api_url)
        # The first column is commonly a hostname even if it is not linked.
        frontend_url = frontend
        clean_name = re.sub(r"\s*\(Official\)\s*", "", display_name, flags=re.I).strip()
        if not frontend_url and "." in clean_name and " " not in clean_name:
            frontend_url = "https://" + clean_name

        out.append({
            "id": f"piped:{api_host}",
            "service": "piped",
            "name": display_name or api_host,
            "url": frontend_url or api_url,
            "api_url": api_url,
            "location": parts[2],
            "cdn": parts[3].lower().startswith("yes"),
            "source": PIPED_RAW,
        })

    if not out:
        raise RuntimeError("No Piped instances discovered")
    return out


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    stamp = now_iso()
    current = {x["id"]: x for x in discover_invidious() + discover_piped()}

    registry = load_json(STATE_PATH, {"instances": {}})
    old = registry.get("instances", {})
    events = load_json(EVENTS_PATH, {"events": []})
    event_list = events.get("events", [])

    for iid, item in current.items():
        previous = old.get(iid)
        if previous is None:
            old[iid] = {
                **item,
                "first_seen": stamp,
                "last_seen": stamp,
                "listed": True,
            }
            event_list.append({"at": stamp, "type": "added", "id": iid, "name": item["name"], "service": item["service"]})
        else:
            old[iid].update(item)
            old[iid]["last_seen"] = stamp
            if not previous.get("listed", True):
                event_list.append({"at": stamp, "type": "relisted", "id": iid, "name": item["name"], "service": item["service"]})
            old[iid]["listed"] = True

    for iid, item in old.items():
        if iid not in current and item.get("listed", True):
            item["listed"] = False
            item["removed_at"] = stamp
            event_list.append({"at": stamp, "type": "removed", "id": iid, "name": item["name"], "service": item["service"]})

    # Keep a bounded event log in git.
    event_list = event_list[-1000:]

    listed = [v for v in old.values() if v.get("listed")]
    save_json(STATE_PATH, {"generated_at": stamp, "instances": old})
    save_json(DISCOVERY_PATH, {"generated_at": stamp, "instances": listed})
    save_json(EVENTS_PATH, {"generated_at": stamp, "events": event_list})

    print(f"Discovered {len(listed)} listed instances ({len(current)} upstream right now).")


if __name__ == "__main__":
    main()
