import os
import time
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))

MODEL_NAME = "llama-3.3-70b-versatile"


def generate_patch(repo_url: str, issue_text: str) -> dict:
    start = time.time()

    prompt = (
        f"Repository: {repo_url}\n"
        f"Issue: {issue_text}\n\n"
        "Generate a unified diff that fixes this issue. "
        "Only return the diff, no explanation."
    )

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
    )
    diff = response.choices[0].message.content

    latency_ms = int((time.time() - start) * 1000)
    quality_score = score_patch(diff)

    return {
        "model_used": MODEL_NAME,
        "generated_diff": diff,
        "quality_score": quality_score,
        "latency_ms": latency_ms,
    }


def score_patch(diff: str) -> float:
    if not diff or len(diff.strip()) < 10:
        return 0.0
    return 75.0
