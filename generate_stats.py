#!/usr/bin/env python3
"""
生成 docs/stats.svg
- 统计每个仓库的 /languages 字节数，按字节总和计算语言占比（更能反映代码量）
- 显示：Top 语言（带百分比与“熟练度”分级）、总 stars、Top 仓库（按 stars）
- 依赖: requests
- 在 Actions 中请通过环境变量传入 USERNAME 和 GITHUB_TOKEN （可选但推荐）
"""
import os
import requests
from datetime import datetime
from math import floor

USERNAME = os.environ.get("USERNAME", "DearIcer")
TOKEN = os.environ.get("GITHUB_TOKEN")
HEADERS = {"Accept": "application/vnd.github.v3+json"}
if TOKEN:
    HEADERS["Authorization"] = f"token {TOKEN}"

API = "https://api.github.com"

def fetch_user(username):
    r = requests.get(f"{API}/users/{username}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()

def fetch_repos(username):
    repos = []
    page = 1
    while True:
        r = requests.get(f"{API}/users/{username}/repos", headers=HEADERS,
                         params={"per_page":100, "page":page, "type":"owner"}, timeout=30)
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        repos.extend(data)
        page += 1
    return repos

def fetch_repo_languages(owner, repo_name):
    r = requests.get(f"{API}/repos/{owner}/{repo_name}/languages", headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()  # {lang: bytes, ...}

def aggregate_languages(repos, owner):
    lang_bytes = {}
    for r in repos:
        try:
            langs = fetch_repo_languages(owner, r['name'])
            for lang, b in langs.items():
                lang_bytes[lang] = lang_bytes.get(lang, 0) + b
        except Exception as e:
            # 若单仓库请求失败，跳过但打印
            print(f"Warning: cannot fetch languages for {r['name']}: {e}")
    total = sum(lang_bytes.values()) or 1
    lang_pct = sorted(
        [(lang, b, b / total * 100.0) for lang, b in lang_bytes.items()],
        key=lambda x: x[1],
        reverse=True
    )
    return lang_pct, total

def aggregate_repo_stats(repos):
    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    top_repos = sorted(repos, key=lambda r: r.get("stargazers_count", 0), reverse=True)[:6]
    return total_stars, top_repos

def level_from_pct(pct):
    # 将百分比映射为熟练度标签（可改）
    if pct >= 40:
        return "Expert"
    if pct >= 20:
        return "Proficient"
    if pct >= 5:
        return "Familiar"
    return "Beginner"

def make_svg(user, total_stars, top_repos, lang_pct, total_bytes):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    name = user.get("name") or user.get("login")
    avatar = user.get("avatar_url")
    followers = user.get("followers", 0)
    public_repos = user.get("public_repos", 0)

    # 画布尺寸与布局
    width = 760
    height = 320
    left_pad = 24
    right_pad = 24
    content_width = width - left_pad - right_pad

    # 取 top N 语言用于展示
    top_langs = lang_pct[:6]

    # SVG 模板（简单样式，方便改）
    bars = ""
    bar_y = 140
    bar_height = 14
    gap = 26
    max_bar_width = 420
    x0 = 170
    for i, (lang, b, pct) in enumerate(top_langs):
        y = bar_y + i * gap
        bar_w = int(max_bar_width * (pct / 100.0))
        pct_label = f"{pct:.1f}%"
        level = level_from_pct(pct)
        # 每一行：语言名、条、百分比、level
        bars += f'''
        <text x="{x0-10}" y="{y+11}" class="lang">{lang}</text>
        <rect x="{x0+70}" y="{y}" width="{max_bar_width}" height="{bar_height}" rx="6" class="bar-bg"/>
        <rect x="{x0+70}" y="{y}" width="{bar_w}" height="{bar_height}" rx="6" class="bar-fill"/>
        <text x="{x0+80+bar_w}" y="{y+11}" class="pct">{pct_label}</text>
        <text x="{x0+70+max_bar_width+10}" y="{y+11}" class="level">{level}</text>
        '''

    # Top repos line
    top_repos_text = "  •  ".join([f"{r['name']} ({r.get('stargazers_count',0)} ⭐)" for r in top_repos])

    svg = f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
  <style>
    .bg{{fill:#0b1220}}
    .card{{fill:#0f1724; stroke:#111827; stroke-width:1}}
    .title{{fill:#fff; font-family:Inter,Segoe UI,Arial; font-size:20px; font-weight:700}}
    .muted{{fill:#9ca3af; font-family:Inter,Segoe UI,Arial; font-size:12px}}
    .stat{{fill:#fff; font-family:Inter,Segoe UI,Arial; font-size:16px; font-weight:600}}
    .lang{{fill:#cbd5e1; font-family:Inter,Segoe UI,Arial; font-size:13px; text-anchor:end}}
    .pct{{fill:#e6edf3; font-family:Inter,Segoe UI,Arial; font-size:12px}}
    .level{{fill:#94a3b8; font-family:Inter,Segoe UI,Arial; font-size:12px}}
    .bar-bg{{fill:#0b2130}}
    .bar-fill{{fill:#3b82f6}}
  </style>

  <rect class="bg" width="100%" height="100%" rx="10"/>
  <g transform="translate(12,12)">
    <rect class="card" x="12" y="12" width="{width-48}" height="{height-24}" rx="10"/>
    <image href="{avatar}" x="36" y="34" height="72" width="72" style="border-radius:8px" />
    <g transform="translate(122,40)">
      <text class="title">{name}</text>
      <text class="muted" y="26">@{USERNAME}</text>

      <g transform="translate(0,56)">
        <text class="stat">⭐ Stars: {total_stars}</text>
        <text class="muted" x="160">📦 Repos: {public_repos}</text>
        <text class="muted" x="320">👥 Followers: {followers}</text>
      </g>
    </g>

    <!-- 语言熟练度条 -->
    <g transform="translate(36,120)">
      <text class="muted" x="0" y="0">Top Languages by code size (total {total_bytes} bytes)</text>
      {bars}
    </g>

    <g transform="translate(36,280)">
      <text class="muted">Top repos:</text>
      <text class="muted" x="96">{top_repos_text}</text>
    </g>

    <text class="muted" x="{width-160}" y="{height-18}">{now}</text>
  </g>
</svg>'''
    return svg

def main():
    user = fetch_user(USERNAME)
    repos = fetch_repos(USERNAME)
    lang_pct, total_bytes = aggregate_languages(repos, USERNAME)
    total_stars, top_repos = aggregate_repo_stats(repos)
    svg = make_svg(user, total_stars, top_repos, lang_pct, total_bytes)
    os.makedirs("docs", exist_ok=True)
    path = os.path.join("docs", "stats.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Generated {path}")

if __name__ == "__main__":
    main()