"""
synthesize.py — LLM synthesis of MetaKG analysis reports via Ollama.
"""

from __future__ import annotations

import httpx

_SYSTEM_PROMPT = """\
You are a metabolic systems biology expert. You will receive a structured analysis \
report of a metabolic knowledge graph. Your task is to synthesize the key findings \
into a concise, actionable scientific narrative suitable for a methods paper. \
Focus on: (1) what the kinetics and topology reveal about metabolic control, \
(2) rate-limiting steps and regulatory bottlenecks, (3) pathway coupling insights, \
(4) gaps and next experiments. Use scientific language. Be direct and specific.\
"""

_USER_TEMPLATE = """\
Please synthesize the following MetaboKG analysis report into a scientific narrative:

{report_text}

Provide:
1. Executive synthesis (3-4 sentences)
2. Key kinetic and regulatory findings
3. Metabolic control points identified
4. Recommended next steps for experimental validation
"""


def synthesize_with_ollama(
    report_text: str,
    *,
    model: str = "llama3.2",
    host: str = "http://localhost:11434",
    timeout: float = 120.0,
) -> str:
    """Send a report to a local Ollama instance and return the synthesized narrative."""
    url = f"{host.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _USER_TEMPLATE.format(report_text=report_text)},
        ],
        "stream": False,
    }
    try:
        resp = httpx.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
    except httpx.ConnectError as exc:
        raise RuntimeError(
            f"Cannot connect to Ollama at {host}. Is it running? (ollama serve)"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Ollama returned {exc.response.status_code}: {exc.response.text}"
        ) from exc

    data = resp.json()
    return data["message"]["content"]
