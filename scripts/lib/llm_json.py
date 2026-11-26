"""Tolerant JSON-object extraction from LLM replies."""

import json


def extract_json_object(text: str) -> dict:
    """Return the first JSON object found in `text`.

    Handles bare JSON, ```json fences, and prose before/after the object.
    Raises ValueError when no object can be decoded (including empty text).
    """
    decoder = json.JSONDecoder()
    for start, ch in enumerate(text or ''):
        if ch != '{':
            continue
        try:
            obj, _ = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    raise ValueError(f'no JSON object in LLM reply: {(text or "")[:200]!r}')
