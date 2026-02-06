import os
import re

ROOT_DIR = r"c:\Users\c23052656\ZeroDay"

DOMAIN_OBJECTS = {
    "Transaction", "Position", "ParsedStatement", "AccountSummary",
    "SourceReference", "BoundingBox", "CorporateAction", "TaxLot"
}

MODEL_OBJECTS = {
    "Job", "JobStatus", "TaxWrapper", "CorporateActionType",
    "TransactionType", "ExtractionMethod", "Organization", "Tenant", "ApiKey", "AdminAuditLog"
}

def process_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    modified = False

    for line in lines:
        # Match: from brokerage_parser.models import ...
        match = re.match(r"^from brokerage_parser\.models import (.+)", line)
        if match:
            # Handle multi-line imports?
            # Simple script assumes single line imports for now based on grep output.
            # If ( is used, grep output showed "from brokerage_parser.models import (" on separate line.
            # Grep showed parens in test_models_uk.py, test_reporting.py.
            # This script might mangle multi-line imports.
            # I should be careful.
            # Let's handle simple one-liners first, and print warnings for parens.

            imports_str = match.group(1).strip()
            if "(" in imports_str:
                print(f"Skipping multi-line import in {filepath}: {line.strip()}")
                new_lines.append(line)
                continue

            # Split by comma
            imports = [i.strip() for i in imports_str.split(",")]

            domain_imports = []
            model_imports = []

            for imp in imports:
                if imp in DOMAIN_OBJECTS:
                    domain_imports.append(imp)
                else:
                    model_imports.append(imp)

            # Construct new lines
            if model_imports:
                new_lines.append(f"from brokerage_parser.models import {', '.join(model_imports)}\n")
            if domain_imports:
                new_lines.append(f"from brokerage_parser.models.domain import {', '.join(domain_imports)}\n")

            modified = True
        else:
            new_lines.append(line)

    if modified:
        print(f"Modifying {filepath}")
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

def walk_and_process():
    for root, dirs, files in os.walk(ROOT_DIR):
        for file in files:
            if file.endswith(".py") and file != "refactor_imports.py":
                process_file(os.path.join(root, file))

if __name__ == "__main__":
    walk_and_process()
