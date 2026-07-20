gi# LLM Persona Ontology

A two-stage pipeline that (1) extracts a structured **persona ontology** from free-text
persona descriptions and (2) **evaluates** how well an LLM plays those personas.

- **`LLMPersonaKG/`** — turns `persona_N.txt` free-text descriptions into 
  ontology YAML (`hasOccupation`, `hasNationality`, `hasGoal`, ...) using
  [OntoGPT](https://github.com/monarch-initiative/ontogpt) + a LinkML schema.
- **`PersonaGym/`** — the [PersonaGym](https://github.com/vsamuel2003/PersonaGym) benchmark,
  adapted here to score personas expressed either as free text **or** as the ontology YAML
  produced in stage 1.

Both stages talk to models through a single **LiteLLM OpenAI-compatible proxy** (configured
via `.env`), so you never edit code to change model or credentials.

---

## 1. Setup

Use one shared `.venv` at the repo root for both `LLMPersonaKG` and `PersonaGym`:

```bash
# from the repo root
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure the model / proxy

Each stage reads its own `.env`. Copy the model id, proxy URL and API key into both:

`LLMPersonaKG/.env`
```dotenv
LLM_MODE=proxy
LITELLM_MODEL=openai/Qwen/Qwen3.6-27B
LITELLM_API_BASE=https://litellm.tools.eurecom.fr/
LITELLM_API_KEY=sk-...
LITELLM_TEMPERATURE=0
LITELLM_MAX_TOKENS=4000
LITELLM_TIMEOUT=180
```

`PersonaGym/.env`
```dotenv
LITELLM_MODEL=openai/Qwen/Qwen3.6-27B
LITELLM_MODEL_EVAL=openai/google/gemma-4-26B-A4B-it
LITELLM_API_BASE=https://litellm.tools.eurecom.fr/v1
LITELLM_API_KEY=sk-...
LITELLM_ENABLE_THINKING=false
```

> `LITELLM_MODEL` is the persona/agent model; `LITELLM_MODEL_EVAL` is the second judge model
> used during scoring. When these are set, `code/run.py` routes everything through the proxy
> automatically (`USE_LITELLM` in `code/api_keys.py`). Leave them unset to fall back to the
> original OpenAI / Anthropic / TogetherAI defaults.

### Verify connectivity (recommended first step)

```bash
cd LLMPersonaKG
python test.py        # prints the resolved config and does one round-trip call
```

---

## 2. Stage 1 — Extract persona ontology (`LLMPersonaKG/`)

Input free-text personas live in `LLMPersonaKG/input/persona_N.txt` (one description per file).

```bash
cd LLMPersonaKG

# 1) Extract raw OntoGPT YAML  ->  output_raw/persona_N.yaml
python run.py

# 2) Clean it (drop empty fields, fix list formatting, restore ontology
#    property names)  ->  output/persona_N.yaml
python clean.py
```

- `run.py` loops over the first `MAX_PERSONAS` (default `10`) inputs and calls
  `ontogpt extract` with `llmp_persona_ontogpt_schema.yaml`. Change `MAX_PERSONAS` to process
  more/fewer files.
- To clean a single file manually:

```bash
python extract_clean_extracted_object.py output_raw/persona_1.yaml output/persona_1.yaml \
  --schema llmp_persona_ontogpt_schema.yaml
```

A cleaned file looks like:

```yaml
persona:
  hasApparentAge: ['71']
  hasOccupation: ['nurse']
  hasNationality: ['Italian']
  hasGoal: ['Advocate for compassionate end-of-life support']
```

The source ontology (`.ttl`) lives in `LLMPersonaKG/ontology/`.

---

## 3. Stage 2 — Evaluate personas (`PersonaGym/`)

All commands run from `PersonaGym/code`. `run.py` picks personas from **one** of the input
flags below, generates (or loads) questions, has the agent model answer them, then scores the
answers with the two judge models. Scores are written to `../scores/<save_name>/scores.json`
and raw Q&A to `../results/<model_name>/`.

```bash
cd PersonaGym/code
```

### Pick your persona source (choose one)

| Flag | Meaning |
|------|---------|
| `--persona_list '["...","..."]'` | Inline Python-style list of free-text personas |
| `--persona_txt <file>` | Single free-text `.txt` persona |
| `--persona_txt_dir ../personaTxt` | Folder of `persona_N.txt` files |
| `--persona_yaml <file>` | Single ontology YAML persona (stage-1 output) |
| `--persona_yaml_dir ../personaOnt` | Folder of `persona_N.yaml` ontology files |
| `--benchmark benchmark-v1` | Run the built-in benchmark persona set |

### Other useful flags

| Flag | Meaning |
|------|---------|
| `--model <id>` | Agent model (defaults to `LITELLM_MODEL` when the proxy is on) |
| `--model_name <name>` | Label used when saving raw responses under `../results/` |
| `--save_name <name>` | Label used when saving scores under `../scores/` |
| `--saved_questions <subdir>` | Reuse pre-generated questions from `../questions/<subdir>` |
| `--saved_responses <dir>` | Score already-generated Q&A instead of calling the agent |
| `--print_prompts` | Print every prompt before it is sent |
| `--dry_run` | Print prompts and skip all LLM calls (no API usage / no cost) |

> When using `--persona_yaml*` or `--persona_txt*`, you must also pass `--benchmark benchmark-v1`
> (or `--saved_questions <subdir>`) so the run can look up the matching saved questions for each
> persona.

### Examples

Evaluate two free-text personas:

```bash
python run.py \
  --persona_list '["an Asian software engineer", "a high school physics teacher"]' \
  --model_name qwen3 --save_name quick_test
```

Run the built-in benchmark:

```bash
python run.py --benchmark benchmark-v1 --model_name qwen3 --save_name benchmark_run
```

Evaluate the ontology personas produced in stage 1 (copy cleaned YAMLs into
`PersonaGym/personaOnt/` first):

```bash
python run.py \
  --persona_yaml_dir ../personaOnt \
  --benchmark benchmark-v1 \
  --model_name qwen3 --save_name ontology_personas
```

Compare against the equivalent free-text personas (`PersonaGym/personaTxt/`):

```bash
python run.py \
  --persona_txt_dir ../personaTxt \
  --benchmark benchmark-v1 \
  --model_name qwen3 --save_name text_personas
```

Do a cost-free dry run to inspect prompts:

```bash
python run.py --persona_txt ../personaTxt/persona_1.txt --benchmark benchmark-v1 --dry_run
```

### Evaluation launch

From `PersonaGym/code`, run both evaluations on the same personas — ontology YAML vs free text:

```bash
# Ontology personas
python3 run.py --benchmark benchmark-v1 --persona_yaml_dir ../personaOnt \
  --model_name qwen3 --save_name ontology_personas

# Free-text personas
python3 run.py --benchmark benchmark-v1 --persona_txt_dir ../personaTxt \
  --model_name qwen3 --save_name text_personas
```

Scores land in `../scores/ontology_personas/` and `../scores/text_personas/`.

---

## 4. End-to-end flow

```
persona_N.txt ─► LLMPersonaKG/run.py ─► output_raw/*.yaml ─► clean.py ─► output/*.yaml
                                                                          │
                          copy free text ─► PersonaGym/personaTxt/        │ copy ontology
                                                                          ▼
                                              PersonaGym/personaOnt/persona_N.yaml
                                                                          │
                                       PersonaGym/code/run.py --persona_yaml_dir ...
                                                                          ▼
                                        scores/<save_name>/scores.json  +  results/<model_name>/
```

The point of the setup is to run stage 2 twice on the *same* personas — once from free text
and once from the extracted ontology — and compare the `PersonaScore` values to see whether the
structured ontology representation helps the model stay in character.
