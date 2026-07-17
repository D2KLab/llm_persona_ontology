from utils import *
from eval_tasks import *
import ast
import argparse
import os
import json
import re
from pathlib import Path
from personas import *
import logging
from api_keys import LITELLM_MODEL, USE_LITELLM
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

try:
    import yaml
except ImportError:
    yaml = None

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# Quiet noisy HTTP client logs during long benchmark runs
for noisy in ("openai", "httpx", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

LITELLM_API_BASE_EVAL = os.getenv("LITELLM_API_BASE_EVAL", LITELLM_API_BASE)
# When LiteLLM is configured (see ../.env), these use the proxy model.
# Otherwise they fall back to the original OpenAI / Together defaults.
if USE_LITELLM:
    SETTINGS_MODEL = os.getenv("LITELLM_MODEL")
    QUESTION_MODEL = os.getenv("LITELLM_MODEL")
    EXAMPLE_MODEL = os.getenv("LITELLM_MODEL")
    EVAL_1 = os.getenv("LITELLM_MODEL")
    EVAL_2 = os.getenv("LITELLM_MODEL_EVAL")
else:
    SETTINGS_MODEL = "gpt-4o-2024-05-13"
    QUESTION_MODEL = "gpt-4o-2024-05-13"
    EXAMPLE_MODEL = "gpt-4o-2024-05-13"
    EVAL_1 = "gpt-4o-2024-05-13"
    EVAL_2 = "meta-llama/Llama-3-70b-chat-hf"

def extract_list(original_string):
    list_string = original_string.replace("```python", "")
    list_string = list_string.replace("```", "")
    list_string = list_string.lstrip().rstrip()
    actual_list = ast.literal_eval(list_string)
    return actual_list


def yaml_to_persona_prompt(yaml_path):
    """Turn a persona ontology YAML into a natural-language identity string."""
    if yaml is None:
        raise RuntimeError("PyYAML is required for --persona_yaml. Install with: pip install pyyaml")

    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)

    persona_obj = data.get("persona", data) if isinstance(data, dict) else data
    if not isinstance(persona_obj, dict):
        raise ValueError(f"Unexpected YAML structure in {yaml_path}")

    lines = ["a person described by the following ontology attributes:"]
    for key, value in persona_obj.items():
        label = re.sub(r"(?<!^)(?=[A-Z])", " ", key.replace("has", "", 1)).strip().lower()
        if isinstance(value, list):
            rendered = ", ".join(str(v) for v in value)
        else:
            rendered = str(value)
        lines.append(f"- {label}: {rendered}")
    return "\n".join(lines)


def resolve_source_persona_text(yaml_path):
    """Map persona_N.yaml -> original free-text persona for question lookup."""
    stem = Path(yaml_path).stem  # persona_1
    root = Path(__file__).resolve().parents[1]  # PersonaGym/
    candidates = [
        root / "personaTxt" / f"{stem}.txt",
    ]
    for path in candidates:
        if path.exists():
            return path.read_text().strip()
    return None


def load_yaml_personas(yaml_dir):
    """Load all persona_*.yaml files from a directory (sorted by numeric id)."""
    yaml_dir = Path(yaml_dir)
    paths = sorted(
        yaml_dir.glob("persona_*.yaml"),
        key=lambda p: int(re.search(r"(\d+)", p.stem).group(1)) if re.search(r"(\d+)", p.stem) else p.stem,
    )
    if not paths:
        raise RuntimeError(f"No persona_*.yaml files found in {yaml_dir}")

    personas = []
    questions_lookup = {}
    labels = []
    for i, path in enumerate(paths):
        prompt = yaml_to_persona_prompt(path)
        source = resolve_source_persona_text(path)
        if source is None:
            raise RuntimeError(f"Could not resolve source text for {path}")
        personas.append(prompt)
        questions_lookup[i] = source
        labels.append(path.stem)
        logger.info(f"Loaded {path.name} -> questions for: {source}")
    return personas, questions_lookup, labels


def _persona_sort_key(path):
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else path.stem


def _has_saved_questions(persona_text, saved_questions):
    if not saved_questions:
        return True
    qpath = Path(__file__).resolve().parent.parent / "questions" / saved_questions / f"{persona_text}.json"
    return qpath.exists()


def load_txt_personas(txt_dir, saved_questions=None):
    """Load persona_*.txt free-text descriptions (sorted by numeric id)."""
    txt_dir = Path(txt_dir)
    paths = sorted(txt_dir.glob("persona_*.txt"), key=_persona_sort_key)
    if not paths:
        raise RuntimeError(f"No persona_*.txt files found in {txt_dir}")

    personas = []
    questions_lookup = {}
    labels = []
    skipped = 0
    for path in paths:
        text = path.read_text().strip()
        if not text:
            logger.warning(f"Skipping empty file {path.name}")
            skipped += 1
            continue
        if not _has_saved_questions(text, saved_questions):
            logger.warning(f"Skipping {path.name}: no questions in {saved_questions}")
            skipped += 1
            continue
        idx = len(personas)
        personas.append(text)
        questions_lookup[idx] = text  # text description is also the question-file key
        labels.append(path.stem)
        logger.info(f"Loaded {path.name}: {text}")

    if not personas:
        raise RuntimeError(
            f"No usable persona_*.txt files in {txt_dir}"
            + (f" with questions in {saved_questions}" if saved_questions else "")
        )
    if skipped:
        logger.info(f"Skipped {skipped} txt files without matching questions")
    return personas, questions_lookup, labels

# Short-listing relevant scenarios/enviornments
def select_settings(persona):
    settings_prompt = f'''
                        Given the following persona description, select the most relevant settings from the given settings options for the persona. Your output must only be the selected settings in a python list format with no other verbose.
                        Persona: {persona}
                        Settings: {settings_list}
                        Selected Settings:
                      '''
    selected_settings  = run_model(input_prompt=settings_prompt, model_card=SETTINGS_MODEL)
    selected_settings = extract_list(selected_settings)    
    return selected_settings

# Generate relevant questions given scenarios
def gen_questions(persona, settings, num_questions=10):
    questions = {task:[] for task in tasks}

    for task in tasks:
        description = question_requirements[task]
        question_prompt = f'''
                            You are tasked with determining if a person with the given persona description is able to answer questions related to {settings} that specifically test the given evaluation task. Generate exactly {num_questions} challenging multi-step questions to do this where the questions are intended to be asked directly to the persona. You may use the question description below to guide you. Your output must be the generated questions in a python list format with no other verbose.
                            Persona: {persona}
                            Settings: {settings}
                            Evaluation Task: {task}
                            Questions Description: {description}
                            Questions: 
                      '''
        for _ in range(5):
            try:
                task_questions  = run_model(input_prompt=question_prompt, model_card=QUESTION_MODEL)
                task_questions = extract_list(task_questions)
            except Exception as e:
                continue
            if len(task_questions) == num_questions:
                break

        
        questions[task].extend(task_questions)

    return questions

def process_examples(text):
    matches = re.findall(r'Score (\d+): *Response - *"?(.*?)"?(?=\n*Score \d+: *Response -|$)', text, re.S)
    processed_text = '\n\n'.join(f'Score {score}: \"{response.strip()}\"' for score, response in matches)

    lines = processed_text.split("\n")
    filtered_lines = [line for line in lines if line.startswith("Score")]

    return "\n\n".join(filtered_lines)

def parse_full_examples(text):
    rubrics = re.split(r'Rubric \d+ Examples:', text)
    if rubrics and rubrics[0].strip() == '':
        rubrics.pop(0)
    rubrics = [rubric.strip() for rubric in rubrics]
    
    return rubrics

def gen_score_examples(persona, qa, rubric, model):
    examples_rubric = open(f'../prompts/score_examples/parallel_examples.txt').read()
    rubrics = []
    for question, _ in qa:
        score_prompt = open(f'../prompts/score_examples/prompt.txt').read()
        score_prompt = score_prompt.format(persona = persona, question = question, rubric = rubric)
        rubrics.append(score_prompt)

    prompt = examples_rubric.format(rubrics=rubrics)

    # vLLM rejects top_p=0; use a tiny positive value for deterministic scoring
    raw = run_model(input_prompt=prompt, temperature=0, top_p=0.01, model_card=model)
    if not raw or raw == "Error":
        logger.warning("Score-example generation failed; continuing with empty examples")
        return [""] * len(qa)

    parsed = parse_full_examples(raw)
    # Normalize each rubric block; pad/truncate to match qa batch size
    examples = [process_examples(block) if block else "" for block in parsed]
    if len(examples) < len(qa):
        logger.warning(
            f"Expected {len(qa)} rubric example blocks, got {len(examples)}; padding"
        )
        examples.extend([""] * (len(qa) - len(examples)))
    return examples[: len(qa)]

def parse_rubric(rubric):
    match_segment = re.search(r"Therefore, the final score is\s*(\d+)", rubric)
    if match_segment:
        return int(match_segment.group(1))
    return 0

def format_rubrics(persona, rubric, qa):
    sys_prompt = open(f'../prompts/rubric_grading/sys_prompt.txt').read()
    prompt_outline = open(f'../prompts/rubric_grading/prompt.txt').read()
    rubrics = []

    examples = gen_score_examples(persona, qa, rubric, EXAMPLE_MODEL)
    for i in range(len(qa)):
        question, answer = qa[i]
        score_examples = examples[i] if i < len(examples) else ""
        formatted_rubric = rubric.format(persona = persona, question = question, response = answer, score_example = score_examples)
        rubrics.append(formatted_rubric)

    
    scoring_prompt = prompt_outline.format(rubrics = rubrics)

    return sys_prompt, scoring_prompt

def parse_evaluations(text):
    pattern = r'\(\d+\) Evaluation:(.*?)(?=\(\d+\) Evaluation:|$)'
    evaluations = re.findall(pattern, text, re.DOTALL)
    evaluations = [eval.strip() for eval in evaluations]
    return evaluations

def calculate_modified_average(score_list):
    total_sum = sum(score_list)
    zero_count = score_list.count(0)
    mod_total = len(score_list) - zero_count

    return total_sum / mod_total if mod_total > 0 else total_sum

def score_rubrics(sys_prompt, scoring_prompt, num_evals=1):
    scores = []

    for _ in range(num_evals):
        evaluator1 = run_model(input_prompt=scoring_prompt, temperature=0, top_p=0.1, model_card=EVAL_1, system = sys_prompt)
        evaluator2 = run_model(input_prompt=scoring_prompt, temperature=0, top_p=0.1, model_card=EVAL_2, system = sys_prompt, api_base=LITELLM_API_BASE_EVAL)

        evaluator1 = parse_evaluations(evaluator1)
        evaluator2 = parse_evaluations(evaluator2)

        scores1 = [parse_rubric(rubric) for rubric in evaluator1]
        scores2 = [parse_rubric(rubric) for rubric in evaluator2]

        score1 = calculate_modified_average(scores1)
        score2 = calculate_modified_average(scores2)

        scores.append(score1)
        scores.append(score2)
    
    return sum(scores) / len(scores)



def gen_answers(persona, questions, model):
    task_to_qa = {}

    for task in tqdm(questions, total=len(questions)):
        task_to_qa[task] = []
        task_questions = questions[task]

        for question in tqdm(task_questions, total=len(task_questions)):
            answer = run_model(input_prompt=question, persona=persona, model_card=model)
            task_to_qa[task].append((question, answer))
    
    return task_to_qa


def score_answers(persona, task_to_qa, score_example=True):
    print(f"Scoring answers for persona: {persona}")
    scores = {task:[] for task in task_to_qa}
    for task in tqdm(task_to_qa):
        for i in tqdm(range(0, len(task_to_qa[task]), 5)):
            selected_qa = task_to_qa[task][i: i + 5]
            rubric = open(f'../rubrics/{task}.txt').read()
            sys_prompt, scoring_prompt = format_rubrics(persona, rubric, selected_qa)

            scores[task].append(score_rubrics(sys_prompt, scoring_prompt))

    
    for task in scores:
        scores[task] = sum(scores[task]) / len(scores[task])
    
    return scores


def _safe_filename(name):
    return re.sub(r'[\\/:*?"<>|\n]+', "_", name)[:180]


def save_responses(persona, task_to_qa, model_name):
    dir = f"../results/{model_name}"
    if not os.path.exists(dir):
        os.makedirs(dir)

    with open(f'{dir}/{_safe_filename(persona)}_qa.json', 'w') as file:
        json.dump(task_to_qa, file, indent=4)

def save_scores(save_name, scores):
    dir = f"../scores/{save_name}"
    if not os.path.exists(dir):
        os.makedirs(dir)

    with open(f'{dir}/scores.json', 'w') as file:
        json.dump(scores, file, indent=4)
      
      
def load_questions(persona, saved_questions):
    dir = f"../questions/{saved_questions}"
    if not os.path.exists(dir):
        print(f"No questions directory {dir}")
        exit(0)
    
    file_path = f'{dir}/{persona}.json'
    if not os.path.exists(file_path):
        print(f"No JSON file {file_path}")
        exit(0)

    with open(file_path, 'r') as file:
        questions = json.load(file)

    return questions

def load_responses(persona, saved_responses): 
    dir = saved_responses
    if not os.path.exists(dir):
        print(f"No responses directory {saved_responses}")
        exit(0)
    
    file_path = f'{dir}/{persona}_qa.json'
    if not os.path.exists(file_path):
        print(f"No JSON file {file_path}")
        exit(0)

    with open(file_path, 'r') as file:
        task_to_qa = json.load(file)

    return task_to_qa
    

def main(persona, model, model_name=None, saved_questions=None, saved_responses=None, questions_persona=None):
    lookup_persona = questions_persona or persona

    if saved_responses:
      task_to_qa = load_responses(lookup_persona, saved_responses)

    else:
      if saved_questions:
        questions = load_questions(lookup_persona, saved_questions)
      else:
        settings = select_settings(persona)
        questions = gen_questions(persona, settings)
        
      task_to_qa = gen_answers(persona, questions, model)
    scores = score_answers(persona, task_to_qa)
    print(scores)
    overall = 0
    for task in scores:
        overall += scores[task]
    
    overall /= len(scores.keys())
    scores["PersonaScore"] = overall

    if model_name:
        save_responses(persona, task_to_qa, model_name)


    return scores


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--persona_list", type=str, help="List of personas", default="[]")
    parser.add_argument("--persona_yaml", type=str, help="Path to a single persona ontology YAML file", default=None)
    parser.add_argument("--persona_yaml_dir", type=str, help="Directory of persona_*.yaml files (e.g. ../personaOnt)", default=None)
    parser.add_argument("--persona_txt", type=str, help="Path to a single free-text persona .txt file", default=None)
    parser.add_argument("--persona_txt_dir", type=str, help="Directory of persona_*.txt files (e.g. ../personaTxt)", default=None)
    default_model = LITELLM_MODEL if USE_LITELLM else "meta-llama/Llama-2-70b-chat-hf"
    parser.add_argument("--model", type=str, help="Model name (LiteLLM proxy id, or OpenAI/Claude/TogetherAI)", default=default_model)
    parser.add_argument("--model_name", help="Model name to save results", default=None)
    parser.add_argument("--saved_questions", help="Path to load in generated questions", default=None)
    parser.add_argument("--saved_responses", help="Path to load in generated question-answer pairs", default=None)
    parser.add_argument("--benchmark", type=str, help="flag for running benchmark (e.g. benchmark-v1)", default=None)
    parser.add_argument("--save_name", type=str, help="unique name to identify saved scores", default="no_name_specified")
    parser.add_argument("--print_prompts", "--print_prompt", action="store_true", help="Print each LLM prompt before calling the API")
    parser.add_argument("--dry_run", action="store_true", help="Print prompts and skip LLM calls (no API usage)")

    args = parser.parse_args()

    import utils as utils_mod
    utils_mod.PRINT_PROMPTS = args.print_prompts or args.dry_run
    utils_mod.DRY_RUN = args.dry_run
    if args.dry_run:
        logger.info("DRY RUN: prompts will be printed; no LLM calls will be made")

    questions_persona_by_idx = {}
    persona_labels = None

    if args.persona_yaml_dir:
        persona_list, questions_persona_by_idx, persona_labels = load_yaml_personas(args.persona_yaml_dir)
        saved_questions = args.benchmark or args.saved_questions
        if not saved_questions:
            raise RuntimeError("Provide --benchmark benchmark-v1 (or --saved_questions) when using --persona_yaml_dir")
        saved_responses = args.saved_responses
    elif args.persona_txt_dir:
        saved_questions = args.benchmark or args.saved_questions
        if not saved_questions:
            raise RuntimeError("Provide --benchmark benchmark-v1 (or --saved_questions) when using --persona_txt_dir")
        persona_list, questions_persona_by_idx, persona_labels = load_txt_personas(
            args.persona_txt_dir, saved_questions=saved_questions
        )
        saved_responses = args.saved_responses
    elif args.persona_yaml:
        yaml_path = args.persona_yaml
        persona_prompt = yaml_to_persona_prompt(yaml_path)
        persona_list = [persona_prompt]
        persona_labels = [Path(yaml_path).stem]
        source_text = resolve_source_persona_text(yaml_path)
        if source_text:
            questions_persona_by_idx[0] = source_text
            logger.info(f"YAML persona from {yaml_path}")
            logger.info(f"Using source text for questions: {source_text}")
        elif args.saved_questions or args.benchmark:
            raise RuntimeError(
                f"Could not resolve source persona text for {yaml_path}. "
                "Needed to load saved questions."
            )
        saved_questions = args.benchmark or args.saved_questions
        saved_responses = args.saved_responses
    elif args.persona_txt:
        txt_path = Path(args.persona_txt)
        text = txt_path.read_text().strip()
        persona_list = [text]
        persona_labels = [txt_path.stem]
        questions_persona_by_idx[0] = text
        saved_questions = args.benchmark or args.saved_questions
        saved_responses = args.saved_responses
        logger.info(f"TXT persona from {txt_path}: {text}")
    elif args.benchmark:
        persona_list = benchmark_personas
        saved_questions = args.benchmark
        saved_responses = None
    else:
        persona_list = eval(args.persona_list)
        saved_questions = args.saved_questions
        saved_responses = args.saved_responses

    results = {}
    all_scores = {}
    for i, persona in tqdm(enumerate(persona_list), total=len(persona_list)):
        label = persona_labels[i] if persona_labels else persona
        scores = main(
            persona,
            args.model,
            args.model_name,
            saved_questions,
            saved_responses,
            questions_persona=questions_persona_by_idx.get(i),
        )
        all_scores[label] = scores
        results[label] = scores["PersonaScore"]
        logger.info(f'Done with {i + 1}/{len(persona_list)} personas ({label})')
        logger.info(f'Scores: {scores}')
    
    
    logger.info(results)
    save_scores(args.save_name, {"PersonaScore": results, "per_persona": all_scores})
    logger.info("Evaluation Done!")
    




