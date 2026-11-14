"""Vision approaches the benchmark can run directly.

* claude: identification-only call with up to three ranked candidates,
  structured output, server-side refusal fallbacks. Cost comes from the token
  usage the API reports.
* openai: the provider already wired in the app (app.routers.vision). It
  returns one answer and the app's call does not keep token usage, so cost is
  not captured.

Approaches that cannot run from Python here (CLIP retrieval from the
Milestone 1 pipeline, on-device ML Kit OCR) write the same results format
themselves and are scored with `bench.py score`.
"""
from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass, field
from typing import Optional

import anthropic

# USD per million tokens (input, output), from the published price list, Nov 2026.
PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


@dataclass
class Outcome:
    candidates: list[dict] = field(default_factory=list)
    latency_s: Optional[float] = None
    cost_usd: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    served_model: Optional[str] = None
    error: Optional[str] = None
    evidence: Optional[str] = None


_nullable = lambda t: {"anyOf": [{"type": t}, {"type": "null"}]}  # noqa: E731

ID_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["candidates", "evidence"],
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "series", "issue_number", "cover_year", "format",
                    "variant_named_on_cover", "printing", "confidence",
                ],
                "properties": {
                    "series": {"type": "string"},
                    "issue_number": {"type": "string"},
                    "cover_year": _nullable("integer"),
                    "format": {"type": "string", "enum": ["single_issue", "annual", "collected_edition", "other"]},
                    "variant_named_on_cover": {"type": "boolean"},
                    "printing": _nullable("string"),
                    "confidence": {"type": "number"},
                },
            },
        },
        "evidence": {"type": "string"},
    },
}

# The rules here are the product spec's, not tuned to the test photos:
# annuals and collected editions are different items from the monthly issue,
# variants are only named when the cover says so, and printings are never
# called from a front cover.
ID_PROMPT = """You identify comic books from a photo of the front cover, for a collector's catalog.

Return up to three candidate issues, most likely first. For each:
- series: the series name as a catalog would list it, without the issue number.
- issue_number: the number printed on the cover.
- cover_year: the cover year if printed or if you know it for that issue, else null.
- format: "annual" if the cover says Annual; "collected_edition" for a hardcover, trade, \
deluxe edition or other collection; "single_issue" for a regular issue; "other" otherwise.
- variant_named_on_cover: true only if the cover itself says it is a variant. Do not \
name variant artists.
- printing: null, unless the cover itself prints a printing such as "2nd printing". \
A printing cannot be told from art or color, so never infer one.
- confidence: 0 to 1.

Watch for series that share words (for example a "New" series versus the original), \
annuals versus the monthly series, and collected editions that reuse an issue number. \
In evidence, say in one or two sentences what on the cover you read."""


def media_type_for(path) -> str:
    return MEDIA_TYPES.get(str(path).lower()[str(path).rfind("."):], "image/jpeg")


def cost_for(model: str, input_tokens: int, output_tokens: int) -> Optional[float]:
    price = PRICES.get(model)
    if not price:
        return None
    return input_tokens / 1e6 * price[0] + output_tokens / 1e6 * price[1]


def parse_claude(response) -> Outcome:
    """Candidates from a Messages API response; refusal checked before content."""
    usage = getattr(response, "usage", None)
    out = Outcome(
        served_model=getattr(response, "model", None),
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
    )
    if out.served_model and out.input_tokens is not None and out.output_tokens is not None:
        out.cost_usd = cost_for(out.served_model, out.input_tokens, out.output_tokens)
    if response.stop_reason == "refusal":
        details = getattr(response, "stop_details", None)
        out.error = f"refused ({getattr(details, 'category', None) or 'no category'})"
        return out
    if response.stop_reason == "max_tokens":
        out.error = "cut off at max_tokens"
        return out
    text = next((b.text for b in response.content if getattr(b, "type", None) == "text"), None)
    try:
        data = json.loads(text or "")
    except json.JSONDecodeError:
        out.error = "response was not JSON"
        return out
    out.candidates = list(data.get("candidates") or [])[:3]
    out.evidence = data.get("evidence")
    if not out.candidates:
        out.error = "no candidates returned"
    return out


async def run_claude(client, image: bytes, media_type: str, model: str, effort: str) -> Outcome:
    start = time.perf_counter()
    try:
        response = await client.beta.messages.create(
            model=model,
            max_tokens=16000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            thinking={"type": "adaptive"},
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": ID_SCHEMA}},
            system=ID_PROMPT,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": media_type,
                        "data": base64.standard_b64encode(image).decode("ascii"),
                    }},
                    {"type": "text", "text": "Identify this comic from its front cover."},
                ],
            }],
        )
    except anthropic.APIStatusError as exc:
        return Outcome(latency_s=time.perf_counter() - start, error=f"API error {exc.status_code}: {exc.message}")
    except anthropic.APIConnectionError:
        return Outcome(latency_s=time.perf_counter() - start, error="could not reach the API")
    out = parse_claude(response)
    out.latency_s = time.perf_counter() - start
    return out


async def run_openai(image: bytes, media_type: str) -> Outcome:
    from app.routers.vision import _openai_analysis  # the app's provider, unchanged

    start = time.perf_counter()
    try:
        r = await _openai_analysis(image, media_type)
    except Exception as exc:  # HTTPException from the app's provider, network errors
        return Outcome(latency_s=time.perf_counter() - start, error=str(getattr(exc, "detail", exc)))
    return Outcome(
        latency_s=time.perf_counter() - start,
        candidates=[{"series": r.title, "issue_number": r.issue_number, "format": "single_issue"}],
        evidence=r.notes,
    )
