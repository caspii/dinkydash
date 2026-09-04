"""The Claude API call.

Structured outputs guarantee the response matches RESPONSE_SCHEMA, so there is
no JSON-repair retry loop here — a malformed response is no longer a thing that
happens. Haiku 4.5 takes no `thinking` parameter, so nothing competes with
max_tokens for room.
"""

import json
import logging

from .prompt import RESPONSE_SCHEMA, SYSTEM_PROMPT

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-haiku-4-5"
DEFAULT_MAX_TOKENS = 1024


class GenerationError(Exception):
    """The model could not be reached, or returned nothing usable."""


def call_claude(user_prompt, config, client=None):
    """Ask Claude for today's headline and note. Returns a dict."""
    if client is None:
        from anthropic import Anthropic
        client = Anthropic()

    model = config.get("claude_model") or DEFAULT_MODEL
    max_tokens = int(config.get("max_tokens") or DEFAULT_MAX_TOKENS)

    log.info("Calling Claude (model=%s, max_tokens=%d)", model, max_tokens)
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            output_config={"format": {"type": "json_schema", "schema": RESPONSE_SCHEMA}},
        )
    except Exception as exc:
        raise GenerationError(f"Claude API call failed: {exc}") from exc

    text = "".join(block.text for block in response.content if block.type == "text")
    if not text.strip():
        raise GenerationError("Claude returned an empty response")

    try:
        content = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GenerationError(f"Claude returned invalid JSON: {exc}") from exc

    usage = getattr(response, "usage", None)
    return {
        "headline": str(content.get("headline", "")).strip(),
        "note": str(content.get("note", "")).strip(),
        "model": model,
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
    }
