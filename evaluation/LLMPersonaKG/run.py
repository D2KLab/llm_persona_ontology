import subprocess
from tqdm import tqdm
import os
from os import path

def main():
    print("Running persona extraction pipeline...")
    files = os.listdir(os.path.join(os.path.dirname(__file__), "input"))

    MAX_PERSONAS = len([f for f in files if f.startswith("persona_") and f.endswith(".txt")])

    path = os.path.dirname(__file__)
    for i in tqdm(range(MAX_PERSONAS)):
        subprocess.run(["ontogpt", "extract", "-t", f"{path}/llmp_persona_ontogpt_schema.yaml","-m","openai/google/gemma-4-31B-it","-i", f"{path}/input/persona_{i+1}.txt", "-o", f"{path}/output_raw/persona_{i+1}.yaml"])

    print("Persona extraction pipeline completed")

if __name__ == "__main__":
    main()
    