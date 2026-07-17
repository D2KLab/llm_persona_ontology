import time
from openai import OpenAI

from api_keys import *

# Set from CLI in run.py
PRINT_PROMPTS = False
DRY_RUN = False


def _normalize_model_card(model_card: str) -> str:
    if model_card.startswith("openai/"):
        return model_card[len("openai/") :]
    return model_card


def _build_messages(input_prompt, persona=None, system=None, message=None):
    if message:
        return message
    if persona:
        persona_prompt = (
            f"Adopt the identity of {persona}\n\n"
            "Answer the questions while staying in strict accordance with the nature of this identity."
        )
        return [
            {"role": "system", "content": persona_prompt},
            {"role": "user", "content": input_prompt},
        ]
    if system:
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": input_prompt},
        ]
    return [{"role": "user", "content": input_prompt}]


def _print_prompt(model_card, messages, temperature, max_tokens, top_p):
    print("\n" + "=" * 80)
    print(f"MODEL: {model_card}")
    print(f"temperature={temperature}  max_tokens={max_tokens}  top_p={top_p}")
    print("-" * 80)
    for msg in messages:
        print(f"[{msg['role'].upper()}]\n{msg['content']}\n")
    print("=" * 80 + "\n", flush=True)


def run_model(
                    input_prompt = None,
                    persona = None,
                    model_card = 'gpt-3.5-turbo',
                    temperature = 0.9, 
                    top_p = 0.9,
                    max_tokens = 3000,
                    message = None,
                    system = None
                ):
    model_card = _normalize_model_card(model_card)

    # Route all calls through the LiteLLM OpenAI-compatible proxy when configured
    if USE_LITELLM:
        return openai_chat_gen(
            input_prompt,
            persona,
            apikey=LITELLM_API_KEY,
            base_url=LITELLM_API_BASE,
            model_card=model_card,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            message=message,
            system=system,
        )

    if "gpt" in model_card:
        return openai_chat_gen(input_prompt, persona, model_card=model_card, temperature=temperature, top_p=top_p, max_tokens = max_tokens, message = message, system=system)
    elif "claude" in model_card:
        return claude_chat_gen(input_prompt, persona=persona, model_card=model_card, temperature=temperature, top_p=top_p, max_tokens = max_tokens)
    elif "llama" in model_card:
        return llama_chat_gen(input_prompt, persona=persona, model_card=model_card, temperature=temperature, top_p=top_p, max_tokens = max_tokens)

def openai_chat_gen(input_prompt = None,
                    persona = None,
                    apikey = OPENAI_API_KEY,
                    model_card = 'gpt-3.5-turbo',
                    temperature = 0.9, 
                    top_p = 0.9,
                    max_tokens = 4000,
                    max_attempt = 3,
                    time_interval = 2,
                    system=None,
                    message = None,
                    base_url = None,
                   ):
    
  
    client_kwargs = {"api_key": apikey}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = OpenAI(**client_kwargs)

    # vLLM requires top_p in (0, 1]
    if top_p is not None and top_p <= 0:
        top_p = 0.01

    message = _build_messages(input_prompt, persona=persona, system=system, message=message)

    if PRINT_PROMPTS or DRY_RUN:
        _print_prompt(model_card, message, temperature, max_tokens, top_p)
    if DRY_RUN:
        return "[DRY_RUN] no LLM call"

    while max_attempt > 0:
        try:
            create_kwargs = {
                "model": model_card,
                "messages": message,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "frequency_penalty": 0,
                "presence_penalty": 0,
                "stop": None,
            }
            # Disable Qwen3/vLLM thinking mode when configured
            if base_url is not None and not LITELLM_ENABLE_THINKING:
                create_kwargs["extra_body"] = {
                    "chat_template_kwargs": {"enable_thinking": False}
                }

            response = client.chat.completions.create(**create_kwargs)
            content = response.choices[0].message.content
            if content is None:
                # Some thinking models may return empty content when truncated
                msg = response.choices[0].message
                content = getattr(msg, "reasoning_content", None)
            return content if content is not None else "Error"

        except Exception as e:

            print('Exception Raised: ', e)

            max_attempt -= 1
            time.sleep(time_interval)

            print('Retrying left: ', max_attempt)

    return 'Error'

def claude_chat_gen(input_prompt,
                    persona = None,
                    apikey = CLAUDE_API_KEY,
                    model_card = 'claude-3-haiku-20240307',
                    temperature = 0, 
                    max_tokens = 4000,
                    max_attempt = 3,
                    time_interval = 5
                   ):
    import anthropic

    assert (type(input_prompt) == str
            ), "claude api does not support batch inference."

  
    client = anthropic.Anthropic(api_key=apikey)

    if persona:
        persona_prompt = f"Adopt the identity of {persona}. Answer the questions while staying in strict accordance with the nature of this identity."
    
    message=[{"role": "user", "content": input_prompt}]
    
    while max_attempt > 0:

        try:
            if persona:
                response = client.messages.create(
                    model= model_card,
                    system = persona_prompt,
                    messages = message,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.content[0].text
            else:
                response = client.messages.create(
                    model= model_card,
                    messages = message,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.content[0].text

        except Exception as e:

            print('Exception Raised: ', e)

            max_attempt -= 1
            time.sleep(time_interval)

            print('Retrying left: ', max_attempt)

    return 'As an AI Model I cannot answer'


def llama_chat_gen(input_prompt,
                   persona = None,
                    apikey = LLAMA_API_KEY,
                    model_card = 'meta-llama/Meta-Llama-3-70B',
                    temperature = 0.9, 
                    top_p = 0.9,
                    max_attempt = 3,
                    time_interval = 5
                   ):
    from together import Together

    assert (type(input_prompt) == str
            ), "openai api does not support batch inference."


    client = Together(api_key=apikey)
    
    if persona:
        persona_prompt = f"Adopt the identity of {persona}. Answer the questions while staying in strict accordance with the nature of this identity."
        message=[{"role": "system", "content": persona_prompt},
                 {"role": "user", "content": input_prompt}]
    else:
        message=[{"role": "user", "content": input_prompt}]
    
    while max_attempt > 0:

        try:
            response = client.chat.completions.create(
                model= model_card,
                messages = message,
                temperature=temperature,
                top_p = top_p,
            )
            return response.choices[0].message.content

        except Exception as e:

            print('Exception Raised: ', e)

            max_attempt -= 1
            time.sleep(time_interval)

            print('Retrying left: ', max_attempt)

    return 'Error'
