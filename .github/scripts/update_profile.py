#!/usr/bin/env python3
"""Keeps three blocks of README.md current, between marker comments (nothing else is touched):

  PROJECTS   featured repositories (list in FEATURED), with description, language and stars
  LANGUAGES  every language used per repository, grouped by area; hides rare ones (< MIN_REPOS)
  RECENT     the newest public repositories that are not featured

With LANGUAGES_TOKEN (can read private repos) private repositories count towards the language
totals; only totals are published, never a private repository name. Without it only public ones count.
"""
import json, os, re, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

OWNER = os.environ.get("OWNER", "fr3on")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
FEATURED = ["portkill", "imbox", "sail", "sutur", "polaris", "laravel-sage"]
RECENT_COUNT = 4
MIN_REPOS = 3
SKIP = {"HTML", "CSS", "SCSS", "Less", "Blade", "Twig", "Smarty", "Dockerfile", "Makefile", "ApacheConf", "Batchfile", "Hack", "PLpgSQL", "Jupyter Notebook"}
GROUPS = [
    ("Backend", ["PHP", "Python", "Ruby", "Java", "C#", "Go"]),
    ("Web", ["JavaScript", "TypeScript", "Vue", "CoffeeScript"]),
    ("Apps & systems", ["Swift", "Rust", "Shell", "C", "C++"]),
]
STYLE = {  # language -> (shields logo slug, colour, logo colour)
    "PHP": ("php", "777BB4", "white"), "Python": ("python", "3776AB", "white"),
    "TypeScript": ("typescript", "3178C6", "white"), "JavaScript": ("javascript", "F7DF1E", "black"),
    "Swift": ("swift", "F05138", "white"), "Rust": ("rust", "000000", "white"),
    "Shell": ("gnubash", "4EAA25", "white"), "Vue": ("vuedotjs", "4FC08D", "white"),
    "Go": ("go", "00ADD8", "white"), "C#": ("csharp", "512BD4", "white"),
    "Ruby": ("ruby", "CC342D", "white"), "Java": ("openjdk", "ED8B00", "white"),
    "Kotlin": ("kotlin", "7F52FF", "white"), "C": ("c", "A8B9CC", "black"), "C++": ("cplusplus", "00599C", "white"),
}


def get(url):
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {})})
            return json.load(urllib.request.urlopen(req, timeout=30))
        except Exception:
            time.sleep(2 * (i + 1))
    return None


def repos():
    base = "https://api.github.com/user/repos?affiliation=owner" if os.environ.get("LANGUAGES_TOKEN") else f"https://api.github.com/users/{OWNER}/repos?type=owner"
    page, out = 1, []
    while True:
        batch = get(f"{base}&per_page=100&page={page}")
        if batch is None:
            sys.exit("could not list repositories; leaving README unchanged")
        out += batch
        if len(batch) < 100:
            return [r for r in out if r["owner"]["login"].lower() == OWNER.lower()]
        page += 1


def badge(lang, n):
    slug, colour, logo_colour = STYLE.get(lang, (None, "555555", "white"))
    label = urllib.parse.quote(lang.replace("-", "--"), safe="")
    logo = f"logo={slug}&logoColor={logo_colour}" if slug else ""
    return f"![{lang}](https://img.shields.io/badge/{label}-{n}%20repos-{colour}?{logo})"


def languages_block(own):
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(lambda r: get(f"https://api.github.com/repos/{r['full_name']}/languages"), own))
    failed = sum(1 for x in results if not isinstance(x, dict))
    if failed > max(2, len(own) // 20):
        sys.exit(f"{failed} of {len(own)} repositories could not be read; leaving README unchanged")
    counts = {}
    for langs in results:
        for lang in langs if isinstance(langs, dict) else []:
            if lang not in SKIP:
                counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        sys.exit("no languages found; leaving README unchanged")
    lines, placed = [], set()
    for title, members in GROUPS:
        items = sorted(((l, counts[l]) for l in members if counts.get(l, 0) >= MIN_REPOS), key=lambda x: (-x[1], x[0]))
        placed.update(members)
        if items:
            lines.append(f"**{title}**<br>\n" + "\n".join(badge(l, n) for l, n in items) + "\n")
    other = sorted(((l, n) for l, n in counts.items() if l not in placed and n >= MIN_REPOS), key=lambda x: (-x[1], x[0]))
    if other:
        lines.append("**Other**<br>\n" + "\n".join(badge(l, n) for l, n in other) + "\n")
    print("languages:", ", ".join(f"{l} {n}" for l, n in sorted(counts.items(), key=lambda x: -x[1])[:12]))
    return "\n".join(lines).rstrip()


def repo_line(r):
    desc = (r.get("description") or "").strip().rstrip(".")
    if len(desc) > 140:
        desc = desc[:137].rsplit(" ", 1)[0] + "..."
    meta = " · ".join(x for x in [r.get("language"), f"★ {r['stargazers_count']}" if r.get("stargazers_count") else ""] if x)
    return f"- **[{r['name']}]({r['html_url']})**" + (f" — {desc}" if desc else "") + (f" <sub>({meta})</sub>" if meta else "")


def projects_block(public):
    by = {r["name"]: r for r in public}
    found = [by[n] for n in FEATURED if n in by]
    missing = [n for n in FEATURED if n not in by]
    if missing:
        print("featured not found (private or renamed):", ", ".join(missing))
    return "\n".join(repo_line(r) for r in found)


def recent_block(public):
    fresh = [r for r in public if not r["fork"] and r["name"] not in FEATURED and r["name"].lower() != OWNER.lower() and not r["name"].startswith(".")]
    fresh.sort(key=lambda r: r["created_at"], reverse=True)
    return "\n".join(repo_line(r) for r in fresh[:RECENT_COUNT])


def replace(text, name, block):
    start, end = f"<!-- {name}:START -->", f"<!-- {name}:END -->"
    if start not in text or end not in text:
        sys.exit(f"markers for {name} not found in README.md")
    return re.sub(re.escape(start) + r".*?" + re.escape(end), lambda m: f"{start}\n{block}\n{end}", text, flags=re.S)


def main():
    allrepos = repos()
    own = [r for r in allrepos if not r.get("fork")]
    public = [r for r in allrepos if not r.get("private")]
    text = open("README.md", encoding="utf-8").read()
    new = replace(text, "LANGUAGES", languages_block(own))
    new = replace(new, "PROJECTS", projects_block(public))
    new = replace(new, "RECENT", recent_block(public))
    if new != text:
        open("README.md", "w", encoding="utf-8").write(new)
        print("README.md updated")
    else:
        print("no change")


main()
