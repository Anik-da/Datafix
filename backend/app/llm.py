"""Optional constrained Groq explanations; deterministic analysis remains primary."""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .config import settings
from .schemas import Issue


class Explanation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hypothesis_id: str
    explanation: str = Field(min_length=1, max_length=500)


_cache: dict[str, Explanation] = {}
_run_counts: dict[str, int] = {}


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def _safe_payload(issue: Issue) -> dict:
    return {
        "category": issue.category.value,
        "title": issue.title,
        "column": issue.column,
        "hypotheses": [{"id": x.id, "statement": x.statement} for x in issue.diagnosis],
        # Exclude observed cell values from the external prompt entirely.
        "evidence": [
            {"label": x.label, "detail": x.detail, "metrics": x.metrics, "examples": []}
            for x in issue.evidence
        ],
    }


def explain_issue(issue: Issue, run_id: str = "") -> str:
    """Return an allowed hypothesis explanation or a deterministic fallback.

    No request can occur unless both LLM_ENABLED=true and a Groq key and model
    are present. Model output cannot add hypotheses, repair values, or code.
    """
    fallback = issue.description
    if not settings.llm_available or not issue.diagnosis:
        return fallback
    payload = _safe_payload(issue)
    cache_key = hashlib.sha256(
        json.dumps({"model": settings.llm_model, "payload": payload}, sort_keys=True).encode()
    ).hexdigest()
    if cache_key in _cache:
        return _cache[cache_key].explanation
    if (
        settings.llm_requests_per_run <= 0
        or _run_counts.get(run_id, 0) >= settings.llm_requests_per_run
    ):
        return fallback
    if len(_run_counts) >= 4096:
        _run_counts.pop(next(iter(_run_counts)))
    _run_counts[run_id] = _run_counts.get(run_id, 0) + 1
    system = (
        "Choose exactly one supplied hypothesis id and write a concise evidence-based explanation. "
        "Return JSON with hypothesis_id and explanation. Do not propose repairs, invent causes, "
        "or include personal data. Explanation must be at most 40 words."
    )
    body = json.dumps(
        {
            "model": settings.llm_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        }
    ).encode()
    engine_version = getattr(settings, "engine_version", "0.1.0")
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"DataFix-Backend/{engine_version}",
        },
        method="POST",
    )
    attempts = max(1, min(settings.llm_max_retries + 1, 3))
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=settings.llm_timeout_seconds) as response:
                result = json.loads(response.read())
            content = result["choices"][0]["message"]["content"]
            parsed = Explanation.model_validate_json(content)
            if (
                parsed.hypothesis_id not in {x.id for x in issue.diagnosis}
                or _word_count(parsed.explanation) > 40
            ):
                return fallback
            if len(_cache) >= 2048:
                _cache.pop(next(iter(_cache)))
            _cache[cache_key] = parsed
            selected = next(x for x in issue.diagnosis if x.id == parsed.hypothesis_id)
            alternatives = [x.statement.rstrip(".") for x in issue.diagnosis if x.id != selected.id]
            # Never expose model-written causal prose: it can overstate certainty even
            # when the selected hypothesis is valid. Render only the validated choice,
            # retain other supplied hypotheses, and explicitly mark them unconfirmed.
            result_text = f"Possible explanation: {selected.statement.rstrip('.')} (not confirmed)."
            if alternatives:
                result_text += " Other possible explanations: " + "; ".join(alternatives) + "."
            return result_text
        except urllib.error.HTTPError as exc:
            # Authentication, model-access and other client errors are
            # deterministic. Retrying a 403 cannot fix permissions and may
            # create duplicate requests; 429 and 5xx responses remain
            # eligible for the bounded retry policy.
            if 400 <= exc.code < 500 and exc.code != 429:
                return fallback
            if attempt + 1 < attempts:
                time.sleep(min(0.2 * (attempt + 1), 0.5))
        except (
            urllib.error.URLError,
            TimeoutError,
            KeyError,
            IndexError,
            ValueError,
            ValidationError,
        ):
            if attempt + 1 < attempts:
                time.sleep(min(0.2 * (attempt + 1), 0.5))
    return fallback
