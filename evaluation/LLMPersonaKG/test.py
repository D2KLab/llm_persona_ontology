import os
import json
from dotenv import load_dotenv
from litellm import completion


def main():
    load_dotenv()

    model = os.getenv("LITELLM_MODEL")
    api_base = os.getenv("LITELLM_API_BASE")
    api_key = os.getenv("LITELLM_API_KEY")

    if not model:
        raise RuntimeError("Missing LITELLM_MODEL in .env")

    print("\n=== TEST CONFIG ===")
    print(f"LITELLM_MODEL: {model}")
    print(f"LITELLM_API_BASE: {api_base}")
    print(f"LITELLM_API_KEY present: {bool(api_key)}")
    print("===================\n")

    kwargs = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": 'Return only this JSON object: {"ok": true}'
            }
        ],
        "temperature": 0,
        "max_tokens": 300,
        "timeout": 60,
    }

    if api_base:
        kwargs["api_base"] = api_base

    if api_key:
        kwargs["api_key"] = api_key

    print("Calling LiteLLM...\n")

    response = completion(**kwargs)

    print("=== RAW RESPONSE ===")
    print(response)
    print("====================\n")

    choice = response["choices"][0]
    message = choice.get("message", {})

    print("=== CHOICE ===")
    print(choice)
    print("==============\n")

    content = message.get("content")

    print("=== CONTENT ===")
    print(repr(content))
    print("===============\n")

    if not content:
        print("ERROR: content is empty.")
        print("finish_reason:", choice.get("finish_reason"))
        print("message:", message)
        return

    try:
        parsed = json.loads(content)
        print("Parsed JSON:", parsed)
    except Exception as e:
        print("Content was not valid JSON.")
        print("JSON error:", e)


if __name__ == "__main__":
    main()