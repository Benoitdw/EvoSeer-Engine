"""Nightly doc audit via Gemini Flash. Opens a GitHub issue if findings."""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
DOCS_DIR = ROOT / "site" / "src" / "content" / "docs"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO = os.environ.get("REPO")

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash-lite:generateContent?key={key}"
)


def collect_docs() -> str:
    parts = []
    for path in sorted(DOCS_DIR.rglob("*.mdx")):
        rel = path.relative_to(ROOT)
        parts.append(f"=== {rel} ===\n{path.read_text()}")
    return "\n\n".join(parts)


def recent_commits() -> str:
    result = subprocess.run(
        ["git", "log", "--since=24 hours ago", "--oneline"],
        capture_output=True, text=True, cwd=ROOT,
    )
    return result.stdout.strip()


def call_gemini(docs: str, commits: str) -> str:
    prompt = f"""You are a documentation quality reviewer for a scientific Python project called EvoSeer Engine.

Recent commits:
{commits}

Documentation files:
{docs}

Review the documentation for:
1. Inconsistencies between docs and recent commits
2. Broken or placeholder links
3. Missing content (e.g. sections marked TODO or "coming soon" that could be filled)
4. Unclear or misleading explanations

Respond with a concise markdown list of findings. If there are no significant issues, respond with exactly: "No significant issues found."
"""
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 1024, "temperature": 0.2},
    }).encode()

    req = urllib.request.Request(
        GEMINI_URL.format(key=GEMINI_API_KEY),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                wait = 30 * (attempt + 1)
                print(f"Rate limited (429), retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"Gemini API error {e.code}: {e.reason}")
                sys.exit(0)
    sys.exit(0)


def open_github_issue(findings: str) -> None:
    body = json.dumps({
        "title": "Doc audit findings",
        "body": f"Automated nightly audit findings:\n\n{findings}",
    }).encode()

    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/issues",
        data=body,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        issue = json.loads(resp.read())
    print(f"Issue opened: {issue['html_url']}")


def main() -> None:
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY not set — skipping audit.")
        sys.exit(0)

    docs = collect_docs()
    commits = recent_commits()
    findings = call_gemini(docs, commits)
    print(findings)

    if findings.strip() != "No significant issues found.":
        open_github_issue(findings)


if __name__ == "__main__":
    main()
