import subprocess
from tqdm import tqdm
import os
from os import path
MAX_PERSONAS = 10

def main():
    print("Running persona cleaning pipeline...")
    files = os.listdir(os.path.join(os.path.dirname(__file__), "output_raw"))
    path = os.path.dirname(__file__)
    for i in tqdm(range(len(files))):
        subprocess.run(["python3", "extract_clean_extracted_object.py", f"{path}/output_raw/persona_{i+1}.yaml", f"{path}/output/persona_{i+1}.yaml"])

    print("Persona cleaning pipeline completed")

if __name__ == "__main__":
    main()
    