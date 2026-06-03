import os
import glob

replacements = {
    "from config import": "from modules.dork_optimizer.utils import",
    "from database import": "from modules.dork_optimizer.db_adapter import",
    "from llm.": "from modules.dork_optimizer.",
    "from services.": "from modules.dork_optimizer.services.",
    "from sources.": "from modules.dork_optimizer.sources.",
}

def replace_in_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    new_content = content
    for old, new in replacements.items():
        new_content = new_content.replace(old, new)
        
    if new_content != content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Updated {filepath}")

base_dir = r"d:\3FI_Tech_AI\Lead_Flow\leadpilot_ai\modules\dork_optimizer"

for root, _, files in os.walk(base_dir):
    for file in files:
        if file.endswith(".py"):
            replace_in_file(os.path.join(root, file))
