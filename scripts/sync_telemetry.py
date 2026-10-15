#!/usr/bin/env python3
"""
DSL-08 Autonomic Telemetry & Repository Card Compiler
Queries GitHub REST API for hamsavartn/{raptor, JanusGate, rtos-edge-gateway}
and dynamically updates assets/telemetry-bar.svg and README.md.
"""
import html
import json
import os
import re
import urllib.request
from datetime import datetime, timezone

USER = "hamsavartn"
REPOS = ["raptor", "JanusGate", "rtos-edge-gateway"]

FALLBACK_DESC = {
    "raptor": "High-performance systems architecture and low-latency execution engine.",
    "JanusGate": "Deterministic dual-interface gateway and boundary control architecture.",
    "rtos-edge-gateway": (
        "Strictly statically allocated, zero-heap FreeRTOS edge gateway on "
        "STM32F103C8T6 (Cortex-M3) with MPU6050, DHT22, ADC & IWDG recovery."
    ),
}


def gh_get(url: str, token: str):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "hamsavartn-dsl08-telemetry")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"[WARN] Failed to fetch {url}: {exc}")
        return None


def fetch_repo_telemetry(repo: str, token: str) -> dict:
    base = f"https://api.github.com/repos/{USER}/{repo}"
    meta = gh_get(base, token) or {}
    langs_data = gh_get(f"{base}/languages", token) or {}
    commits = gh_get(f"{base}/commits?per_page=1", token)

    latest_sha = "HEAD"
    commit_date = "ACTIVE"
    if isinstance(commits, list) and len(commits) > 0:
        latest_sha = commits[0].get("sha", "HEAD")[:7].upper()
        raw_date = (
            commits[0]
            .get("commit", {})
            .get("committer", {})
            .get("date", "")
        )
        if raw_date:
            commit_date = raw_date[:10]

    top_langs = list(langs_data.keys())[:4]
    if not top_langs and meta.get("language"):
        top_langs = [meta["language"]]
    if not top_langs:
        top_langs = ["Systems", "Architecture"]

    desc = meta.get("description") or FALLBACK_DESC.get(repo, "Systems engineering repository.")
    stars = meta.get("stargazers_count", 0)
    size_kb = meta.get("size", 0)

    return {
        "name": repo,
        "url": f"https://github.com/{USER}/{repo}",
        "description": desc,
        "primary_lang": top_langs[0],
        "langs": top_langs,
        "sha": latest_sha,
        "date": commit_date,
        "stars": stars,
        "size_kb": size_kb,
    }


def build_telemetry_svg(records: list) -> str:
    accents = ["#C8A25A", "#3B82F6", "#10B981"]
    xs = [28, 428, 828]
    slots = []

    for idx, rec in enumerate(records):
        x = xs[idx]
        color = accents[idx % len(accents)]
        title = html.escape(f"0x0{idx+1} // {rec['name']}")
        sub = html.escape(
            f"LANG: {rec['primary_lang'].upper()} • SHA: {rec['sha']} • UPD: {rec['date']}"
        )
        slots.append(
            f'  <circle cx="{x}" cy="26" r="3.5" fill="{color}"/>\n'
            f'  <text x="{x+12}" y="30" fill="#F1F5F9" font-size="12" font-weight="700" class="mono">{title}</text>\n'
            f'  <text x="{x}" y="52" fill="#94A3B8" font-size="10.5" class="mono">{sub}</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 76" width="100%" height="76">
  <style>
    .mono {{ font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace; }}
  </style>
  <rect width="1200" height="76" rx="8" fill="#07090E" stroke="#1E2430" stroke-width="1.2"/>
  <line x1="400" y1="12" x2="400" y2="64" stroke="#161C28" stroke-width="1"/>
  <line x1="800" y1="12" x2="800" y2="64" stroke="#161C28" stroke-width="1"/>
{chr(10).join(slots)}
</svg>
"""


def build_readme_cards(records: list) -> str:
    cells = []
    for idx, rec in enumerate(records):
        reg_addr = f"0x0800_0{idx+1}00"
        desc = html.escape(rec["description"])
        badges = " ".join(f"<code>{html.escape(l)}</code>" for l in rec["langs"])
        cells.append(
            f'    <td width="33%" valign="top">\n'
            f'      <h4><code>[0x0{idx+1}]</code> <a href="{rec["url"]}"><strong>{html.escape(rec["name"])}</strong></a></h4>\n'
            f'      <p><sub><code>REG: {reg_addr}</code> • <code>SHA: {rec["sha"]}</code> • <code>{rec["date"]}</code></sub></p>\n'
            f'      <p>{desc}</p>\n'
            f'      <p>{badges}</p>\n'
            f'    </td>'
        )
    return (
        "<!-- DYNAMIC_PROJECTS_START -->\n"
        '<table width="100%">\n  <tr>\n'
        + "\n".join(cells)
        + "\n  </tr>\n</table>\n"
        "<!-- DYNAMIC_PROJECTS_END -->"
    )


def main():
    token = os.environ.get("GITHUB_TOKEN", "")
    records = [fetch_repo_telemetry(r, token) for r in REPOS]

    os.makedirs("assets", exist_ok=True)
    with open("assets/telemetry-bar.svg", "w", encoding="utf-8") as f:
        f.write(build_telemetry_svg(records))

    with open("README.md", "r", encoding="utf-8") as f:
        readme = f.read()

    new_block = build_readme_cards(records)
    updated_readme = re.sub(
        r"<!-- DYNAMIC_PROJECTS_START -->.*?<!-- DYNAMIC_PROJECTS_END -->",
        new_block,
        readme,
        flags=re.DOTALL,
    )

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(updated_readme)

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[OK] Synced telemetry for {', '.join(REPOS)} at {now_str}")


if __name__ == "__main__":
    main()
