#!/usr/bin/env python3
import datetime as dt
import html
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

USERNAME = os.getenv("PROFILE_USERNAME", "Selmi-Med-Dhia")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT_DIR = Path("profile")
OUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "profile-metrics-generator",
}


def request_json(url: str, *, method: str = "GET", payload=None):
    data = None
    headers = dict(HEADERS)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def rest(path: str):
    return request_json(f"https://api.github.com{path}")


def graphql(query: str, variables: dict):
    result = request_json(
        "https://api.github.com/graphql",
        method="POST",
        payload={"query": query, "variables": variables},
    )
    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"], indent=2))
    return result["data"]


def all_public_repos():
    repos = []
    page = 1
    encoded = urllib.parse.quote(USERNAME, safe="")
    while True:
        batch = rest(
            f"/users/{encoded}/repos?type=owner&sort=updated&per_page=100&page={page}"
        )
        repos.extend(batch)
        if len(batch) < 100:
            return repos
        page += 1


def search_count(query: str) -> int:
    encoded = urllib.parse.urlencode({"q": query, "per_page": 1})
    return int(rest(f"/search/issues?{encoded}")["total_count"])


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def fmt_number(value: int) -> str:
    return f"{value:,}"


def write_stats(metrics: dict, refreshed: str):
    cards = [
        ("Contributions", fmt_number(metrics["contributions"]), "last 365 days"),
        ("Current streak", f'{metrics["current_streak"]} days', "GitHub contribution days"),
        ("Longest streak", f'{metrics["longest_streak"]} days', "within the last 365 days"),
        ("Public repos", fmt_number(metrics["public_repos"]), "owned repositories"),
        ("Public stars", fmt_number(metrics["stars"]), "across non-fork repos"),
        ("Pull requests", fmt_number(metrics["pull_requests"]), "opened publicly"),
        ("Issues", fmt_number(metrics["issues"]), "opened publicly"),
        ("Followers", fmt_number(metrics["followers"]), "public profile"),
    ]

    width, height = 900, 286
    item_w, item_h = 205, 78
    start_x, start_y = 20, 96
    gap_x, gap_y = 13, 12

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="GitHub profile statistics for {esc(USERNAME)}">',
        "<style>",
        ".title{font:700 22px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;fill:#00E5FF}",
        ".sub{font:400 12px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;fill:#8B949E}",
        ".label{font:600 12px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;fill:#8B949E}",
        ".value{font:700 24px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;fill:#C9D1D9}",
        ".note{font:400 10px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;fill:#6E7681}",
        "</style>",
        '<rect x="0.5" y="0.5" width="899" height="285" rx="14" fill="#0D1117" stroke="#21262D"/>',
        '<text x="24" y="34" class="title">&gt; github.telemetry</text>',
        f'<text x="24" y="58" class="sub">GitHub-native public data · refreshed {esc(refreshed)} UTC</text>',
        '<line x1="24" y1="76" x2="876" y2="76" stroke="#21262D"/>',
    ]

    for index, (label, value, note) in enumerate(cards):
        row, col = divmod(index, 4)
        x = start_x + col * (item_w + gap_x)
        y = start_y + row * (item_h + gap_y)
        parts.extend(
            [
                f'<rect x="{x}" y="{y}" width="{item_w}" height="{item_h}" rx="10" fill="#0B141B" stroke="#1F2D35"/>',
                f'<text x="{x + 14}" y="{y + 21}" class="label">{esc(label)}</text>',
                f'<text x="{x + 14}" y="{y + 49}" class="value">{esc(value)}</text>',
                f'<text x="{x + 14}" y="{y + 67}" class="note">{esc(note)}</text>',
            ]
        )

    parts.append("</svg>")
    (OUT_DIR / "stats.svg").write_text("\n".join(parts), encoding="utf-8")


def write_contributions(weeks: list, refreshed: str):
    width, height = 900, 188
    cell, gap = 11, 3
    origin_x, origin_y = 112, 57
    colors = ["#161B22", "#003547", "#005F73", "#00A6C7", "#00E5FF"]
    weekday_labels = {1: "Mon", 3: "Wed", 5: "Fri"}

    max_count = max(
        (int(day.get("contributionCount", 0)) for week in weeks for day in week["contributionDays"]),
        default=0,
    )

    def level(count: int) -> int:
        if count <= 0:
            return 0
        if max_count <= 4:
            return min(count, 4)
        ratio = count / max_count
        if ratio <= 0.25:
            return 1
        if ratio <= 0.5:
            return 2
        if ratio <= 0.75:
            return 3
        return 4

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="GitHub contribution heatmap for {esc(USERNAME)}">',
        "<style>",
        ".title{font:700 17px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;fill:#00E5FF}",
        ".sub{font:400 10px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;fill:#8B949E}",
        ".axis{font:400 9px ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;fill:#8B949E}",
        "</style>",
        '<rect x="0.5" y="0.5" width="899" height="187" rx="14" fill="#0D1117" stroke="#21262D"/>',
        '<text x="24" y="31" class="title">&gt; contribution.calendar</text>',
        f'<text x="876" y="31" text-anchor="end" class="sub">refreshed {esc(refreshed)} UTC</text>',
    ]

    for row, label in weekday_labels.items():
        y = origin_y + row * (cell + gap) + 9
        parts.append(f'<text x="100" y="{y}" text-anchor="end" class="axis">{label}</text>')

    seen_months = set()
    for week_index, week in enumerate(weeks):
        x = origin_x + week_index * (cell + gap)
        for day in week["contributionDays"]:
            date = dt.date.fromisoformat(day["date"])
            count = int(day["contributionCount"])
            weekday = (date.weekday() + 1) % 7  # Sunday=0, matching GitHub's calendar rows.
            y = origin_y + weekday * (cell + gap)
            fill = colors[level(count)]
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{fill}"><title>{esc(date)}: {count} contributions</title></rect>'
            )
            month_key = (date.year, date.month)
            if date.day <= 7 and month_key not in seen_months:
                seen_months.add(month_key)
                parts.append(
                    f'<text x="{x}" y="49" class="axis">{date.strftime("%b")}</text>'
                )

    legend_x = 711
    parts.append('<text x="668" y="171" class="axis">Less</text>')
    for idx, color in enumerate(colors):
        parts.append(
            f'<rect x="{legend_x + idx * 17}" y="161" width="11" height="11" rx="2" fill="{color}"/>'
        )
    parts.append('<text x="806" y="171" class="axis">More</text>')
    parts.append("</svg>")
    (OUT_DIR / "contributions.svg").write_text("\n".join(parts), encoding="utf-8")


def main():
    now = dt.datetime.now(dt.timezone.utc)
    today = now.date()
    start_day = today - dt.timedelta(days=364)
    start = dt.datetime.combine(start_day, dt.time.min, tzinfo=dt.timezone.utc)
    end = dt.datetime.combine(today, dt.time.max, tzinfo=dt.timezone.utc)

    profile = rest(f"/users/{urllib.parse.quote(USERNAME, safe='')}")
    repos = all_public_repos()
    stars = sum(int(repo.get("stargazers_count", 0)) for repo in repos if not repo.get("fork"))
    pull_requests = search_count(f"author:{USERNAME} type:pr")
    issues = search_count(f"author:{USERNAME} type:issue")

    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    data = graphql(
        query,
        {
            "login": USERNAME,
            "from": start.isoformat().replace("+00:00", "Z"),
            "to": end.isoformat().replace("+00:00", "Z"),
        },
    )
    calendar = data["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = calendar["weeks"]
    counts = {
        dt.date.fromisoformat(day["date"]): int(day["contributionCount"])
        for week in weeks
        for day in week["contributionDays"]
        if start_day <= dt.date.fromisoformat(day["date"]) <= today
    }

    streak_end = today
    if counts.get(streak_end, 0) == 0:
        streak_end -= dt.timedelta(days=1)
    current_streak = 0
    cursor = streak_end
    while cursor >= start_day and counts.get(cursor, 0) > 0:
        current_streak += 1
        cursor -= dt.timedelta(days=1)

    longest_streak = 0
    running = 0
    cursor = start_day
    while cursor <= today:
        if counts.get(cursor, 0) > 0:
            running += 1
            longest_streak = max(longest_streak, running)
        else:
            running = 0
        cursor += dt.timedelta(days=1)

    metrics = {
        "contributions": int(calendar["totalContributions"]),
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "public_repos": int(profile["public_repos"]),
        "stars": stars,
        "pull_requests": pull_requests,
        "issues": issues,
        "followers": int(profile["followers"]),
    }

    refreshed = now.strftime("%Y-%m-%d %H:%M")
    write_stats(metrics, refreshed)
    write_contributions(weeks, refreshed)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
