import subprocess
from tqdm import tqdm
import os
from os import path
MAX_PERSONAS = 10

def main():
    print("Running persona extraction pipeline...")
    files = os.listdir(os.path.join(os.path.dirname(__file__), "input"))
    path = os.path.dirname(__file__)
    for i in tqdm(range(MAX_PERSONAS)):
        subprocess.run(["ontogpt", "extract", "-t", f"{path}/llmp_persona_ontogpt_schema.yaml","-m","openai/Qwen/Qwen3.6-27B","-i", f"{path}/input/persona_{i+1}.txt", "-o", f"{path}/output_raw/persona_{i+1}.yaml"])

    print("Persona extraction pipeline completed")

if __name__ == "__main__":
    main()
    