#!/usr/bin/env python3
"""Rewrites the Languages section of README.md from the owner's non-fork repositories.

Every language a repository uses counts once for that repository. With a token that can read
private repositories (LANGUAGES_TOKEN) those are counted too; only the totals are published,
never a repository name. Without it, only public repositories are counted. Markup, styling
and config languages are skipped. Only the text between the two marker comments changes.
"""
import json, os, re, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

OWNER = os.environ.get("OWNER", "fr3on")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
START, END = "<!-- LANGUAGES:START -->", "<!-- LANGUAGES:END -->"
SKIP = {"HTML", "CSS", "SCSS", "Less", "Blade", "Twig", "Smarty", "Dockerfile", "Makefile", "ApacheConf", "Batchfile", "Hack", "PLpgSQL", "Jupyter Notebook"}
# language -> (shields logo slug, colour, logo colour)
STYLE = {
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
    logo = f"&logo={slug}&logoColor={logo_colour}" if slug else ""
    return f"![{lang}](https://img.shields.io/badge/{label}-{n}%20repos-{colour}?{logo.lstrip('&')})"


def main():
    own = [r for r in repos() if not r.get("fork")]
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(lambda r: get(f"https://api.github.com/repos/{r['full_name']}/languages"), own))
    failed = sum(1 for x in results if not isinstance(x, dict))
    if failed > max(2, len(own) // 20):
        sys.exit(f"{failed} of {len(own)} repositories could not be read; leaving README unchanged")
    counts = {}
    for langs in results:
        if not isinstance(langs, dict):
            continue
        for lang in langs:
            if lang not in SKIP:
                counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        sys.exit("no languages found; leaving README unchanged")
    ordered = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:12]
    block = "\n".join(badge(l, n) for l, n in ordered)
    text = open("README.md", encoding="utf-8").read()
    if START not in text or END not in text:
        sys.exit("markers not found in README.md")
    new = re.sub(re.escape(START) + r".*?" + re.escape(END), f"{START}\n{block}\n{END}", text, flags=re.S)
    if new != text:
        open("README.md", "w", encoding="utf-8").write(new)
        print("updated:", ", ".join(f"{l} {n}" for l, n in ordered))
    else:
        print("no change")


main()
