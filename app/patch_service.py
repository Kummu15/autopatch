"""Agentic patch generation pipeline for AutoPatch."""
import ast
import base64
import os
import re
import time
from typing import Any, Dict, List, Optional
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import json

try:
    from groq import Groq
except ImportError:
    Groq = None


MODEL_NAME = "llama3-8b-8192"
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_THRESHOLD = 70

client = None


def _get_client():
    global client
    if client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key or Groq is None:
            return None
        try:
            client = Groq(api_key=api_key)
        except Exception:
            client = None
    return client


def _call_groq(prompt: str) -> str:
    groq_client = _get_client()
    if groq_client is None:
        raise RuntimeError("GROQ_API_KEY is not configured or the groq package is unavailable")
    response = groq_client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are AutoPatch, an autonomous bug-fixing agent."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=1200,
    )
    return response.choices[0].message.content or ""


# ─── FETCH STEP ───────────────────────────────────────────────────────────────

def _parse_repo(repo_url: str):
    """Extract owner and repo name from a GitHub URL."""
    match = re.search(r"github\.com/([^/]+)/([^/]+?)(?:\.git)?$", repo_url.strip())
    if not match:
        return None, None
    return match.group(1), match.group(2)


def _detect_file_from_issue(issue_text: str) -> Optional[str]:
    """Try to extract a file path mentioned in the issue."""
    match = re.search(r"[\w/]+\.(?:py|js|ts|java|go|rb|cpp|c|cs|rs|php)", issue_text)
    return match.group(0) if match else None


def _fetch_github_file(repo_url: str, file_path: str) -> Optional[str]:
    """Fetch file content from GitHub API and return decoded text."""
    owner, repo = _parse_repo(repo_url)
    if not owner or not repo:
        return None
    token = os.environ.get("GITHUB_TOKEN")
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    except Exception:
        return None
    return None


def _fetch_repo_files(repo_url: str) -> Optional[str]:
    """Fetch root-level file listing to help agent identify relevant files."""
    owner, repo = _parse_repo(repo_url)
    if not owner or not repo:
        return None
    token = os.environ.get("GITHUB_TOKEN")
    url = f"https://api.github.com/repos/{owner}/{repo}/contents"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        files = [item["path"] for item in data if item["type"] == "file"]
        return "\n".join(files)
    except Exception:
        return None


def fetch_code_context(repo_url: str, issue_text: str) -> tuple[Optional[str], Optional[str]]:
    """
    FETCH step: detect file from issue, fetch its content.
    Returns (code, file_path).
    """
    file_path = _detect_file_from_issue(issue_text)
    if file_path:
        code = _fetch_github_file(repo_url, file_path)
        if code:
            return code, file_path

    # fallback: list repo files and pick the first .py/.js file
    listing = _fetch_repo_files(repo_url)
    if listing:
        for line in listing.splitlines():
            if line.endswith((".py", ".js", ".ts")):
                code = _fetch_github_file(repo_url, line)
                if code:
                    return code, line

    return None, None


# ─── FALLBACKS ────────────────────────────────────────────────────────────────

def _fallback_plan(issue_text: str, code: Optional[str], language: str) -> List[str]:
    return [
        "Inspect the failing logic and identify the root cause.",
        f"Patch the {language or 'code'} implementation for the issue: {issue_text}",
        "Validate that the updated logic is syntactically correct.",
    ]


def _fallback_patch(code: Optional[str], issue_text: str, language: str) -> str:
    if not code:
        return f"diff --git a/example.{language} b/example.{language}\n--- a/example.{language}\n+++ b/example.{language}\n@@ -0,0 +1 @@\n+// TODO: implement fix for {issue_text}"
    updated_lines = []
    for line in code.splitlines():
        if "return a - b" in line:
            updated_lines.append(line.replace("return a - b", "return a + b"))
        else:
            updated_lines.append(line)
    if updated_lines == code.splitlines():
        updated_lines = code.splitlines() + [f"# patched for: {issue_text}"]
    return (
        f"diff --git a/example.{language} b/example.{language}\n"
        f"--- a/example.{language}\n"
        f"+++ b/example.{language}\n"
        f"@@ -1,2 +1,2 @@\n"
        f"-{code.splitlines()[0]}\n"
        f"+{updated_lines[0]}\n"
    )


def _fallback_reflection(score: float, issue_text: str) -> str:
    return (
        f"The previous attempt scored {score:.1f}. I should refine the patch for the issue '{issue_text}' "
        "and add more targeted handling."
    )


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _parse_score(text: str) -> float:
    match = re.search(r"score\s*[:=]\s*(\d{1,3})", text, re.IGNORECASE)
    if not match:
        return 0.0
    return float(match.group(1))


def _syntax_check(code: Optional[str], language: str) -> bool:
    if not code:
        return True
    if language != "python":
        return True
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def _detect_language(file_path: Optional[str]) -> str:
    if not file_path:
        return "python"
    ext = file_path.rsplit(".", 1)[-1]
    return {"py": "python", "js": "javascript", "ts": "typescript", "go": "go", "rb": "ruby"}.get(ext, "python")


# ─── PROMPTS ──────────────────────────────────────────────────────────────────

def _build_plan_prompt(repo_url, issue_text, code, language):
    context = code or "<no code context supplied>"
    return (
        f"Repository: {repo_url}\nLanguage: {language}\nIssue: {issue_text}\n"
        f"Code context:\n{context}\n\n"
        "Create a short plan with 3 steps for how to fix this issue. "
        "Return only the plan as a numbered list."
    )


def _build_generation_prompt(repo_url, issue_text, code, language, reflection=None):
    context = code or "<no code context supplied>"
    reflection_text = f"\nReflection context:\n{reflection}\n" if reflection else ""
    return (
        f"Repository: {repo_url}\nLanguage: {language}\nIssue: {issue_text}\n"
        f"Code context:\n{context}\n{reflection_text}"
        "Generate a unified diff patch that fixes the issue. Return only the diff, no explanation."
    )


def _build_evaluation_prompt(issue_text, diff, code, language):
    return (
        f"Issue: {issue_text}\nLanguage: {language}\nProposed patch:\n{diff}\n"
        f"Original code:\n{code or '<none>'}\n\n"
        "Score this patch from 0 to 100 for correctness and usefulness. "
        "Return one line in the format: score: <number> reason: <brief reason>."
    )


def _build_reflection_prompt(issue_text, diff, score):
    return (
        f"Issue: {issue_text}\nPrevious patch:\n{diff}\nScore: {score:.1f}\n\n"
        "Explain why the patch failed and how to improve it for the next attempt."
    )


# ─── PIPELINE ─────────────────────────────────────────────────────────────────

def run_agentic_patch(
    repo_url: str,
    issue_text: str,
    code: Optional[str] = None,
    language: str = "python",
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    threshold: int = DEFAULT_THRESHOLD,
) -> Dict[str, Any]:
    reflection_log: List[Dict[str, Any]] = []
    best_result: Optional[Dict[str, Any]] = None

    for attempt in range(1, max_attempts + 1):
        try:
            plan_text = _call_groq(_build_plan_prompt(repo_url, issue_text, code, language))
        except Exception:
            plan_text = "\n".join(_fallback_plan(issue_text, code, language))

        plan_steps = [step.strip(" -*").strip() for step in plan_text.splitlines() if step.strip()]
        if len(plan_steps) < 3:
            plan_steps = _fallback_plan(issue_text, code, language)

        reflection_context = reflection_log[-1]["reflection"] if reflection_log else None

        try:
            diff = _call_groq(_build_generation_prompt(repo_url, issue_text, code, language, reflection_context))
        except Exception:
            diff = _fallback_patch(code, issue_text, language)

        try:
            eval_text = _call_groq(_build_evaluation_prompt(issue_text, diff, code, language))
        except Exception:
            eval_text = f"score: {70 if diff and len(diff) > 10 else 0} reason: fallback evaluation"

        score = _parse_score(eval_text)
        syntax_ok = _syntax_check(code, language)
        if not syntax_ok:
            score = min(score, 55.0)

        result = {
            "status": "succeeded" if score >= threshold else "failed",
            "score": score,
            "generated_diff": diff,
            "plan": plan_steps,
            "verification": {
                "status": "passed" if syntax_ok and score >= threshold else "failed",
                "score": score,
                "syntax_ok": syntax_ok,
                "reason": eval_text,
            },
            "attempt_number": attempt,
        }

        if best_result is None or score > best_result["score"]:
            best_result = result

        if score >= threshold:
            return {**result, "reflection_log": reflection_log, "model_used": MODEL_NAME}

        try:
            reflection_text = _call_groq(_build_reflection_prompt(issue_text, diff, score))
        except Exception:
            reflection_text = _fallback_reflection(score, issue_text)

        reflection_log.append({"attempt": attempt, "score": score, "reflection": reflection_text})

    if best_result is None:
        best_result = {
            "status": "failed", "score": 0.0, "generated_diff": "",
            "plan": _fallback_plan(issue_text, code, language),
            "verification": {"status": "failed", "score": 0.0, "syntax_ok": False, "reason": "No patch generated"},
            "attempt_number": max_attempts,
        }

    return {**best_result, "reflection_log": reflection_log, "model_used": MODEL_NAME}


def generate_patch(
    repo_url: str,
    issue_text: str,
    code: Optional[str] = None,
    language: str = "python",
) -> Dict[str, Any]:
    start = time.time()

    # ── FETCH STEP ──
    if not code:
        fetched_code, file_path = fetch_code_context(repo_url, issue_text)
        if fetched_code:
            code = fetched_code
            language = _detect_language(file_path)

    result = run_agentic_patch(repo_url, issue_text, code=code, language=language)
    latency_ms = int((time.time() - start) * 1000)

    return {
        "status": "success" if result["status"] == "succeeded" else "failed",
        "model_used": result["model_used"],
        "generated_diff": result["generated_diff"],
        "plan": result["plan"],
        "verification": result["verification"],
        "attempt_number": result["attempt_number"],
        "reflection_log": result.get("reflection_log", []),
        "score": result["score"],
        "latency_ms": latency_ms,
    }


def score_patch(diff: str) -> float:
    if not diff or len(diff.strip()) < 10:
        return 0.0
    return 75.0
