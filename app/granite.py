"""
granite.py – IBM Granite via watsonx.ai.
If API keys are absent or a network error occurs the function returns
a safe template string so the rest of the app keeps working.
"""

import os
import urllib.request
import urllib.error
import json

# Read credentials from environment variables (optional).
_API_KEY = os.environ.get("WATSONX_API_KEY", "")
_PROJECT_ID = os.environ.get("WATSONX_PROJECT_ID", "")
_URL = os.environ.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")

# watsonx.ai generation endpoint.
_GENERATE_URL = f"{_URL}/ml/v1/text/generation?version=2023-05-29"
# IBM IAM token endpoint.
_IAM_URL = "https://iam.cloud.ibm.com/identity/token"

# Model to use (IBM Granite 13b instruct).
_MODEL_ID = "ibm/granite-13b-instruct-v2"

# Template used when Granite is unavailable.
_FALLBACK = (
    "Educational summary unavailable (Granite not configured). "
    "Review the evidence table and gaps section above for key findings. "
    "All findings are based on fictional data for educational use only."
)


def _get_iam_token() -> str:
    """Exchange the API key for a short-lived IAM bearer token."""
    body = (
        f"grant_type=urn%3Aibm%3Aparams%3Aoauth%3Agrant-type%3Aapikey"
        f"&apikey={_API_KEY}"
    ).encode()
    req = urllib.request.Request(
        _IAM_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["access_token"]


def explain(summary: str) -> tuple[str, str]:
    """
    Ask Granite to explain the clinical decision-support summary.

    Returns (text, source) where source is "granite" or "template".
    Falls back to template text on any error.
    """
    if not _API_KEY or not _PROJECT_ID:
        return _FALLBACK, "template"

    try:
        token = _get_iam_token()

        prompt = (
            "You are an educational clinical decision-support assistant. "
            "The following is a fictional AI-generated differential diagnosis summary. "
            "Write a concise plain-English explanation (3-5 sentences) highlighting "
            "the key uncertainties and why clinician review is essential. "
            "Never state a confirmed diagnosis. "
            "Always note this is fictional educational material.\n\n"
            f"Summary:\n{summary}\n\nExplanation:"
        )

        payload = json.dumps(
            {
                "model_id": _MODEL_ID,
                "input": prompt,
                "parameters": {
                    "decoding_method": "greedy",
                    "max_new_tokens": 200,
                    "stop_sequences": ["\n\n"],
                },
                "project_id": _PROJECT_ID,
            }
        ).encode()

        req = urllib.request.Request(
            _GENERATE_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            text = result["results"][0]["generated_text"].strip()
            return text, "granite"

    except Exception:
        # Network errors, key errors, timeouts – degrade gracefully.
        return _FALLBACK, "template"
