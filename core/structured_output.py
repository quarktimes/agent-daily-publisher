"""
Structured Output — JSON Schema enforced agent outputs.

Why this exists:
  Free-text agent communication is fragile. When Agent A passes data
  to Agent B, both need a shared contract. JSON Schema is that contract.

  This module provides:
    1. SchemaValidator — validate dicts against JSON Schema
    2. StructuredFormatter — format schema instructions for LLM prompts
    3. extract_structured — parse and validate LLM responses
"""

import json
import re
from typing import Any


class SchemaValidationError(Exception):
    """Raised when structured output fails schema validation."""


class SchemaValidator:
    """Validate Python dicts against JSON Schema (draft-07 subset)."""

    def __init__(self, schema: dict[str, Any]):
        self.schema = schema
        self._required = set(schema.get("required", []))
        self._properties = schema.get("properties", {})

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate data against schema. Returns data on success, raises on failure."""
        errors = []

        # Check required fields
        for field in self._required:
            if field not in data or data[field] is None:
                errors.append(f"Missing required field: '{field}'")

        # Check type constraints
        for key, value in data.items():
            if key in self._properties:
                prop = self._properties[key]
                if "type" in prop:
                    error = self._check_type(key, value, prop["type"])
                    if error:
                        errors.append(error)

        if errors:
            raise SchemaValidationError("; ".join(errors))
        return data

    def _check_type(self, key: str, value: Any, expected: str) -> str | None:
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        py_type = type_map.get(expected)
        if py_type and not isinstance(value, py_type):
            return f"Field '{key}': expected {expected}, got {type(value).__name__}"
        return None

    def format_schema_instruction(self) -> str:
        """Generate an LLM prompt fragment that describes the expected output schema."""
        return f"""You MUST respond with a valid JSON object matching this schema:
```json
{json.dumps(self.schema, indent=2, ensure_ascii=False)}
```

Rules:
- Return ONLY a JSON object — no markdown fences, no explanation, no preamble.
- All required fields must be present and non-null.
- Use null for optional fields that are not applicable.
"""


def extract_json(text: str) -> dict:
    """Extract a JSON object from arbitrary text (handles markdown fences, wrapping text)."""
    # Try direct parse first
    text = text.strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # Try extracting from markdown code blocks
    pattern = r"```(?:json)?\s*\n?([\s\S]*?)```"
    matches = re.findall(pattern, text)
    for match in reversed(matches):
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # Try finding {...} in text
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        try:
            return json.loads(text[brace_start : brace_end + 1])
        except json.JSONDecodeError:
            pass

    raise SchemaValidationError("No valid JSON object found in response")
