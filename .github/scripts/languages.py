#!/usr/bin/env python3
"""Rewrites the Languages section of README.md from the owner's public, non-fork repositories.

Counts each repository once, by its primary language as GitHub reports it. Markup and
styling languages are skipped. Only the text between the two marker comments changes.
"""
import json, os, re, sys, urllib.parse, urllib.request

OWNER = os.environ.get("OWNER", "fr3on")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
START, END = "<!-- LANGUAGES:START -->", "<!-- LANGUAGES:END -->"
SKIP = {"HTML", "CSS", "SCSS", "Less", "Blade", "Dockerfile", "Makefile", "Jupyter Notebook"}
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


def repos():
    page, out = 1, []
    while True:
        url = f"https://api.github.com/users/{OWNER}/repos?type=owner&per_page=100&page={page}"
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {})})
        batch = json.load(urllib.request.urlopen(req, timeout=30))
        out += batch
        if len(batch) < 100:
            return out
        page += 1


def badge(lang, n):
    slug, colour, logo_colour = STYLE.get(lang, (None, "555555", "white"))
    label = urllib.parse.quote(lang.replace("-", "--"), safe="")
    logo = f"&logo={slug}&logoColor={logo_colour}" if slug else ""
    return f"![{lang}](https://img.shields.io/badge/{label}-{n}%20repos-{colour}?{logo.lstrip('&')})"


def main():
    counts = {}
    for r in repos():
        lang = r.get("language")
        if r.get("fork") or r.get("private") or r.get("archived") or not lang or lang in SKIP:
            continue
        counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        sys.exit("no languages found; leaving README unchanged")
    ordered = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:10]
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
