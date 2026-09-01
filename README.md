# Tube Instance Watch

An automated GitHub Pages dashboard for public **Invidious** and **Piped** instances.

The project follows upstream instance lists automatically. When an upstream project adds a new public instance, the next scheduled run discovers it without a manual edit. Removed and relisted instances are tracked as events.

## What it checks

- Upstream discovery
- API reachability
- HTTP status
- Response latency from GitHub Actions
- Real playback-metadata extraction using a stable public test video
- First seen / last seen timestamps
- Added / removed / relisted events
- Rolling 24-hour, 7-day and 30-day success rates
- A simple 0–100 health score
- Best-effort browser-side reachability testing

A successful playback check means the backend returned JSON playback metadata for the test video at that moment. It does **not** guarantee every YouTube video will play.

## Automatic data flow

```text
Official Invidious list ─┐
                         ├─> discover.py ─> registry.json + events.json
Official Piped list ─────┘                       |
                                                 v
                                            checker.py
                                                 |
                                                 v
                                          status.json
                                                 |
                                                 v
                                      build_site_data.py
                                                 |
                                                 v
                                        instances.json
                                                 |
                                                 v
                                          GitHub Pages
```

GitHub Actions runs this pipeline every hour.

## Upstream discovery

### Invidious
The project parses the official public-instance section at:

`https://docs.invidious.io/instances/`

### Piped
The project parses TeamPiped's public-instance table from:

`https://github.com/TeamPiped/documentation`

The table provides the Piped API URL, location and CDN information.

## Files

- `discover.py` — discovers new, removed and relisted instances.
- `checker.py` — checks API health, latency and playback extraction.
- `build_site_data.py` — combines current state with rolling history.
- `data/registry.json` — persistent known-instance registry.
- `data/events.json` — bounded added/removed/relisted event log.
- `data/history/YYYY-MM-DD.jsonl` — compact probe history.
- `data/instances.json` — public frontend data file.

## Deploy on GitHub Pages

1. Create a repository and add these files.
2. Replace `yourname` in the User-Agent strings with your GitHub username/repository URL.
3. Push to `main`.
4. Open **Settings → Pages**.
5. Choose **Deploy from a branch**.
6. Select `main` and `/ (root)`.
7. Open **Actions** and run **Discover and monitor instances** once manually.
8. After the action commits the first dataset, the Pages site will populate automatically.

## Notes about GitHub Actions history

Hourly JSONL history is intentionally compact, but a long-running project will still grow over time because history is committed to Git. For a small public-instance list this is fine initially. If the project becomes popular or history grows substantially, move long-term measurements to a lightweight database or artifact store and keep only aggregates in Git.

## Privacy and trust

Tube Instance Watch does not operate any Invidious or Piped instance and does not proxy visitor traffic.

Public instances are third-party services. Their operators control their own logging, retention and privacy policies.

The optional **Test from my browser** button makes a direct browser request to an instance. CORS or browser security rules can cause this test to fail even when the instance itself works.

## License

MIT
