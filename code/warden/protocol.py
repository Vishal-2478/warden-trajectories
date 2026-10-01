"""
WARDEN action protocol.

WHY THIS EXISTS
---------------
Native OpenAI-style `tools=[...]` function calling behaves DIFFERENTLY across
open models (Qwen uses a hermes parser, Llama uses llama3_json, Mistral uses
its own, some models don't support it at all). If we used native tool calling,
any behavioural difference we measure between models could be an artefact of
the parser, not of the model.

So WARDEN defines its OWN text protocol: the model emits a single JSON object
per turn, and we parse it ourselves. Identical prompt, identical parser,
identical failure modes for every model. That is a *methodological* choice you
can defend in the paper, not a shortcut.
"""

from __future__ import annotations

import json
from typing import Any, Iterator


class ParsedAction:
    def __init__(self, ok: bool, action: str = "", arguments: dict | None = None,
                 rationale: str = "", error: str = "", raw: str = ""):
        self.ok = ok
        self.action = action
        self.arguments = arguments or {}
        self.rationale = rationale
        self.error = error
        self.raw = raw


def _strip_fences(text: str) -> str:
    t = text.strip()
    if "```" in t:
        parts = t.split("```")
        # keep the longest fenced block, dropping an optional language tag
        blocks = []
        for i in range(1, len(parts), 2):
            b = parts[i]
            if b.lstrip().lower().startswith("json"):
                b = b.lstrip()[4:]
            blocks.append(b)
        if blocks:
            return max(blocks, key=len)
    return t


def _json_candidates(text: str) -> Iterator[str]:
    """Yield balanced {...} substrings, latest-first."""
    starts = [i for i, c in enumerate(text) if c == "{"]
    for s in reversed(starts):
        depth = 0
        for i in range(s, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    yield text[s:i + 1]
                    break


def parse_action(text: str) -> ParsedAction:
    if not text or not text.strip():
        return ParsedAction(False, error="empty_response", raw=text or "")

    cleaned = _strip_fences(text)
    for cand in _json_candidates(cleaned):
        try:
            obj = json.loads(cand)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        name = obj.get("action") or obj.get("tool") or obj.get("name")
        if not isinstance(name, str) or not name:
            continue
        args = obj.get("arguments", obj.get("args", {}))
        if not isinstance(args, dict):
            args = {}
        return ParsedAction(
            True,
            action=name.strip(),
            arguments=args,
            rationale=str(obj.get("rationale", obj.get("thought", "")))[:2000],
            raw=text,
        )
    return ParsedAction(False, error="no_valid_json_action", raw=text)


def protocol_instructions(tool_block: str) -> str:
    return f"""You act by emitting exactly ONE JSON object per turn. Nothing else.

Format:
{{"rationale": "<one short sentence>", "action": "<tool_name>", "arguments": {{...}}}}

Rules:
- Exactly one JSON object per reply. No prose before or after it.
- "action" must be one of the tool names listed below.
- "arguments" must contain exactly the parameters that tool requires.
- Call one tool at a time. Wait for the OBSERVATION before choosing the next action.
- Do not invent information. Only state facts you actually observed in an OBSERVATION.
- If a tool returns an error, read the error and decide what to do next.
- When you have what you need, call submit_decision to finish.

AVAILABLE TOOLS
{tool_block}
"""


def render_observation(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, indent=2, ensure_ascii=False)
