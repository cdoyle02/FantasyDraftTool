"""Summarize large ESPN payloads into something a model can actually read.

A single league request with a player view can exceed several megabytes, so the
default exploration mode returns a structural outline rather than raw JSON.
"""

from __future__ import annotations

import json
from typing import Any

MAX_KEYS = 60
SAMPLE_STRING = 60


def describe(value: Any, *, depth: int = 4, _level: int = 0) -> Any:
    if _level >= depth:
        return _leaf_name(value)

    if isinstance(value, dict):
        keys = list(value.keys())
        described: dict[str, Any] = {
            key: describe(value[key], depth=depth, _level=_level + 1) for key in keys[:MAX_KEYS]
        }
        if len(keys) > MAX_KEYS:
            described[f"...{len(keys) - MAX_KEYS} more keys"] = "truncated"
        return described

    if isinstance(value, list):
        if not value:
            return "list[0]"
        return {
            f"list[{len(value)}] of": describe(value[0], depth=depth, _level=_level + 1),
        }

    return _leaf_name(value)


def _leaf_name(value: Any) -> str:
    if isinstance(value, bool):
        return f"bool({value})"
    if isinstance(value, int):
        return f"int({value})"
    if isinstance(value, float):
        return f"float({value})"
    if value is None:
        return "null"
    if isinstance(value, str):
        sample = value if len(value) <= SAMPLE_STRING else value[:SAMPLE_STRING] + "..."
        return f"str({sample!r})"
    if isinstance(value, dict):
        return f"dict[{len(value)} keys]"
    if isinstance(value, list):
        return f"list[{len(value)}]"
    return type(value).__name__


def render_json(value: Any, max_chars: int) -> str:
    text = json.dumps(value, indent=2, default=str)
    if len(text) <= max_chars:
        return text
    return (
        text[:max_chars]
        + f"\n... truncated, {len(text) - max_chars} characters omitted. "
        + "Re-run with mode='shape', a narrower view, or a smaller limit."
    )
