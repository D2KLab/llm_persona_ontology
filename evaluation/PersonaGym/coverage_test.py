"""Check whether text persona information is represented in ontology values.

One LLM call is made per matching persona. The result is written as a CSV with
one row per atomic piece of information:

    personaId,info,inText,inYaml

Run from the repository root, for example:

    .venv/bin/python PersonaGym/coverage_test.py
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any
from tqdm import tqdm
import yaml


# Reuse the same model/API setup as PersonaGym/code/run.py without importing
# run.py itself (which would start the benchmark argument parser).
CODE_DIR = Path(__file__).resolve().parent / "code"
sys.path.insert(0, str(CODE_DIR))
from api_keys import LITELLM_MODEL, USE_LITELLM  # noqa: E402
from utils import run_model  # noqa: E402


DEFAULT_TEXT_DIR = Path("PersonaGym/personaTxt")
DEFAULT_YAML_DIR = Path("PersonaGym/personaOnt")
DEFAULT_OUTPUT = Path("PersonaGym/coverage_results.csv")


def persona_number(path: Path) -> int:
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else 10**9


def load_personas(text_dir: Path, yaml_dir: Path) -> list[tuple[str, str, str]]:
    """Return matching (persona ID, text, YAML) records in numeric order."""
    text_files = {path.stem: path for path in text_dir.glob("persona_*.txt")}
    yaml_files = {path.stem: path for path in yaml_dir.glob("persona_*.yaml")}
    persona_ids = sorted(text_files.keys() & yaml_files.keys(), key=lambda p: persona_number(Path(p)))

    records = []
    for persona_id in persona_ids:
        text = text_files[persona_id].read_text(encoding="utf-8").strip()
        yaml_data = yaml.safe_load(yaml_files[persona_id].read_text(encoding="utf-8"))
        yaml_text = yaml.safe_dump(yaml_data, sort_keys=False, allow_unicode=True)
        records.append((persona_id, text, yaml_text))
    return records


def build_prompt(persona_id: str, text: str, yaml_text: str) -> str:
    return f"""You are evaluating coverage of a structured persona ontology.

Compare the original free-text persona with the ontology YAML below. Extract
every concrete, atomic piece of persona information mentioned in either source.
Examples include age, occupation, location, interests, goals, preferences,
roles, identity, and activities. Split different facts into separate rows.

For each fact, mark whether it is present or clearly represented in the text
and whether it is present or clearly represented in the YAML values. Do not
infer facts that are not stated. Treat synonyms and direct paraphrases as a
match (for example, "nurse" and "nursing"), but do not treat vaguely related
concepts as a match.

Return ONLY valid JSON. The JSON must be an array of objects with exactly these
keys and boolean values for the last two keys:
[
  {{"info": "age: 71", "inText": true, "inYaml": true}}
]

Persona ID: {persona_id}

ORIGINAL TEXT:
{text}

ONTOLOGY YAML:
{yaml_text}
"""


def extract_json_array(response: str) -> list[dict[str, Any]]:
    """Parse a JSON array, including arrays wrapped in markdown fences."""
    response = response.strip().replace("```json", "").replace("```", "").strip()
    start, end = response.find("["), response.rfind("]")
    if start < 0 or end <= start:
        raise ValueError(f"LLM response did not contain a JSON array: {response[:200]}")
    parsed = json.loads(response[start : end + 1])
    if not isinstance(parsed, list):
        raise ValueError("LLM response JSON is not an array")

    rows: list[dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict) or not isinstance(item.get("info"), str):
            raise ValueError(f"Invalid coverage row: {item!r}")
        if not isinstance(item.get("inText"), bool) or not isinstance(item.get("inYaml"), bool):
            raise ValueError(f"Coverage flags must be booleans: {item!r}")
        rows.append({"info": item["info"].strip(), "inText": item["inText"], "inYaml": item["inYaml"]})
    return rows


def evaluate_persona(persona_id: str, text: str, yaml_text: str, model: str) -> list[dict[str, Any]]:
    """Make one LLM request for one persona and parse its coverage rows."""
    prompt = build_prompt(persona_id, text, yaml_text)
    response = run_model(input_prompt=prompt, model_card=model, temperature=0, top_p=0.01)
    return extract_json_array(response)


def write_csv(output_path: Path, rows: list[dict[str, Any]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["personaId", "info", "inText", "inYaml"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text-dir", type=Path, default=DEFAULT_TEXT_DIR)
    parser.add_argument("--yaml-dir", type=Path, default=DEFAULT_YAML_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--model",
        default=LITELLM_MODEL if USE_LITELLM else "gpt-4o-2024-05-13",
        help="LLM model name; defaults to the model configured for PersonaGym.",
    )
    parser.add_argument("--limit", type=int, help="Process only the first N personas.")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    text_dir = args.text_dir if args.text_dir.is_absolute() else project_root / args.text_dir
    yaml_dir = args.yaml_dir if args.yaml_dir.is_absolute() else project_root / args.yaml_dir
    output = args.output if args.output.is_absolute() else project_root / args.output

    records = load_personas(text_dir, yaml_dir)
    if args.limit is not None:
        records = records[: args.limit]
    if not records:
        raise RuntimeError("No matching persona_*.txt and persona_*.yaml files found")

    output_rows: list[dict[str, Any]] = []
    for index, (persona_id, text, yaml_text) in tqdm(enumerate(records, start=1), total=len(records), desc="Evaluating personas"):
        #print(f"[{index}/{len(records)}] Evaluating {persona_id}...", flush=True)
        try:
            coverage_rows = evaluate_persona(persona_id, text, yaml_text, args.model)
        except Exception as error:
            print(f"  ERROR: {error}", file=sys.stderr)
            continue
        for row in coverage_rows:
            output_rows.append({"personaId": persona_number(Path(persona_id)), **row})

    write_csv(output, output_rows)
    print(f"Wrote {len(output_rows)} rows to {output}")


if __name__ == "__main__":
    main()
