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


def collect_code_diff() -> str:
    """Return the diff of Python source files changed in the last commit."""
    result = subprocess.run(
        ["git", "diff", "HEAD~1", "HEAD", "--", "evoseer/"],
        capture_output=True, text=True, cwd=ROOT,
    )
    diff = result.stdout.strip()
    # Cap at ~15 000 chars to stay within token limits
    if len(diff) > 15_000:
        diff = diff[:15_000] + "\n... (truncated)"
    return diff


def collect_docs() -> str:
    """Return all documentation content, capped at ~10 000 chars."""
    parts = []
    total_chars = 0
    for path in sorted(DOCS_DIR.rglob("*.mdx")):
        content = path.read_text()
        total_chars += len(content)
        if total_chars > 10_000:
            break
        rel = path.relative_to(ROOT)
        parts.append(f"=== {rel} ===\n{content}")
    return "\n\n".join(parts)


def recent_commits() -> str:
    result = subprocess.run(
        ["git", "log", "--since=24 hours ago", "--oneline"],
        capture_output=True, text=True, cwd=ROOT,
    )
    return result.stdout.strip()


def call_model(docs: str, code_diff: str) -> str:
    if not code_diff:
        return "No significant issues found."

    prompt = f"""You are a documentation quality reviewer for a scientific Python project called EvoSeer Engine.

The following Python source code was changed in the latest commit:
<diff>
{code_diff}
</diff>

Current documentation:
<docs>
{docs}
</docs>

Check whether the documentation needs to be updated to reflect the code changes. Look for:
1. New classes, methods, or parameters in the diff that are not documented
2. Renamed or removed things that are still mentioned in the docs
3. Behaviour changes that contradict what the docs describe

Respond with a concise markdown list of doc updates needed. If the docs are already up to date, respond with exactly: "No significant issues found."
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

    code_diff = collect_code_diff()
    if not code_diff:
        print("No Python source changes in last commit — skipping audit.")
        sys.exit(0)

    docs = collect_docs()
    findings = call_model(docs, code_diff)
    print(findings)

    if findings.strip() != "No significant issues found.":
        open_github_issue(findings)


if __name__ == "__main__":
    main()
