"""Nightly doc audit via GitHub Models. Opens a GitHub issue if findings."""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
DOCS_DIR = ROOT / "site" / "src" / "content" / "docs"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO = os.environ.get("REPO")

GH_MODELS_URL = "https://models.inference.ai.azure.com/chat/completions"


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


def call_model(docs: str, commits: str) -> str:
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
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
        "temperature": 0.2,
    }).encode()

    req = urllib.request.Request(
        GH_MODELS_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GITHUB_TOKEN}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        print(f"GitHub Models API error {e.code}: {body_text}")
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
    try:
        with urllib.request.urlopen(req) as resp:
            issue = json.loads(resp.read())
        print(f"Issue opened: {issue['html_url']}")
    except urllib.error.HTTPError as e:
        print(f"Failed to open issue {e.code}: {e.read().decode()}")


def main() -> None:
    if not GITHUB_TOKEN:
        print("GITHUB_TOKEN not set — skipping audit.")
        sys.exit(0)

    docs = collect_docs()
    commits = recent_commits()
    findings = call_model(docs, commits)
    print(findings)

    if findings.strip() != "No significant issues found.":
        open_github_issue(findings)


if __name__ == "__main__":
    main()
