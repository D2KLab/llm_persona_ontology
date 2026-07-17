#!/usr/bin/env python3
"""
Extract only `extracted_object` from an OntoGPT YAML output file,
remove empty fields, unwrap bracketed list-like strings, and optionally
rename snake_case fields back to ontology camelCase terms using a LinkML schema.

Usage:
  python extract_clean_extracted_object.py persona_output.yaml persona_cleaned.yaml
  python extract_clean_extracted_object.py persona_output.yaml persona_cleaned.yaml --schema llmp_persona_ontogpt_schema_fixed_internal_snake.yaml

Output:
  extracted_object:
    hasApparentAge:
      - "34"
    hasOccupation:
      - "software engineer"
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml


EMPTY_STRINGS = {"", "[]", "[ ]", "null", "none", "None", "NULL", "~"}


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_yaml(data: Any, path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True, width=1000)


def is_empty_scalar(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() in EMPTY_STRINGS
    return False


def split_bracketed_string(value: str) -> list[str]:
    """
    Converts strings produced by OntoGPT like:
      '[34]' -> ['34']
      '[software engineer]' -> ['software engineer']
      '[evidence-based decisions, careful planning, low-risk choices]'
        -> ['evidence-based decisions', 'careful planning', 'low-risk choices']
      '[]' -> []
    """
    text = value.strip()

    if text in EMPTY_STRINGS:
        return []

    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        # Split simple OntoGPT bracketed lists on commas.
        # This intentionally avoids complex YAML parsing because OntoGPT often removes quotes.
        parts = [p.strip().strip('"\'') for p in inner.split(",")]
        return [p for p in parts if p and p not in EMPTY_STRINGS]

    return [text]


def clean_value(value: Any) -> list[str]:
    if is_empty_scalar(value):
        return []

    if isinstance(value, str):
        return split_bracketed_string(value)

    if isinstance(value, list):
        cleaned: list[str] = []
        for item in value:
            cleaned.extend(clean_value(item))
        # deduplicate while preserving order
        seen = set()
        result = []
        for item in cleaned:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result

    # Keep non-string scalar values as strings for robust downstream RDF conversion.
    if isinstance(value, (int, float, bool)):
        return [str(value)]

    # Skip dicts because this workflow expects string-only OntoGPT extraction.
    return []


def snake_to_lower_camel_after_prefix(name: str) -> str:
    """Fallback: has_apparent_age -> hasApparentAge, uses_decision_criterion -> usesDecisionCriterion."""
    parts = name.split("_")
    if not parts:
        return name
    if len(parts) == 1:
        return name
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def build_schema_mapping(schema_path: Path | None) -> dict[str, str]:
    """
    Build mapping from internal LinkML attribute names to ontology property local names.
    Example: has_apparent_age -> hasApparentAge from slot_uri: llmp:hasApparentAge
    """
    if schema_path is None:
        return {}

    schema = load_yaml(schema_path)
    mapping: dict[str, str] = {}

    classes = schema.get("classes", {}) if isinstance(schema, dict) else {}
    for class_def in classes.values():
        if not isinstance(class_def, dict):
            continue
        attrs = class_def.get("attributes", {}) or {}
        for attr_name, attr_def in attrs.items():
            if not isinstance(attr_def, dict):
                continue
            slot_uri = attr_def.get("slot_uri")
            if not slot_uri or not isinstance(slot_uri, str):
                continue
            local = re.split(r"[#:/]", slot_uri)[-1]
            if local:
                mapping[attr_name] = local

    return mapping


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_yaml", type=Path)
    parser.add_argument("output_yaml", type=Path)
    parser.add_argument("--schema", type=Path, default=None, help="Optional LinkML schema used to restore ontology property names from slot_uri.")
    parser.add_argument("--keep-snake-case", action="store_true", help="Do not rename fields to ontology camelCase terms.")
    parser.add_argument("--include-source-text", action="store_true", help="Keep source_text in the cleaned output.")
    args = parser.parse_args()

    data = load_yaml(args.input_yaml)
    if not isinstance(data, dict):
        raise ValueError("Input YAML must be a mapping/object.")

    extracted = data.get("extracted_object")
    if not isinstance(extracted, dict):
        raise ValueError("No extracted_object mapping found in input YAML.")

    schema_mapping = build_schema_mapping(args.schema)
    cleaned: dict[str, list[str]] = {}

    for key, value in extracted.items():
        if key == "source_text" and not args.include_source_text:
            continue
        if key == "has_personal_description":
            continue
        if key == "has_social_description":
            continue
        if key == "has_behavior_description":
            continue
        values = clean_value(value)
        if not values:
            continue

        if args.keep_snake_case:
            out_key = key
        else:
            out_key = schema_mapping.get(key, snake_to_lower_camel_after_prefix(key))

        cleaned[out_key] = values

    save_yaml({"persona": cleaned}, args.output_yaml)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
