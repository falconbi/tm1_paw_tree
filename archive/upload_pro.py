import json
import re

def parse_ti_file(file_path):
    """
    Parse a TM1 TI file into sections and parameters for PAW.
    """
    sections = {"Prolog": "", "Metadata": "", "Data": "", "Epilog": ""}
    parameters = []

    current_section = "Prolog"
    with open(file_path, 'r') as f:
        for line in f:
            # Detect section headers (simple heuristic)
            if re.match(r'#\s*Metadata', line, re.I):
                current_section = "Metadata"
                continue
            elif re.match(r'#\s*Data', line, re.I):
                current_section = "Data"
                continue
            elif re.match(r'#\s*Epilog', line, re.I):
                current_section = "Epilog"
                continue

            sections[current_section] += line

            # Detect parameter definitions like pStartYear = "2022"
            param_match = re.match(r'(\w+)\s*=\s*["\']?([\w\d]+)["\']?', line)
            if param_match:
                name, value = param_match.groups()
                # Avoid duplicates
                if not any(p['Name'] == name for p in parameters):
                    parameters.append({
                        "Name": name,
                        "Prompt": "",
                        "Value": str(value),
                        "Type": "String"
                    })

    return sections, parameters

def build_paw_json(process_name, sections, parameters):
    """
    Build the PAW-compatible JSON for the process.
    """
    payload = {
        "Name": process_name,
        "HasSecurityAccess": False,
        "PrologProcedure": sections.get("Prolog", ""),
        "MetadataProcedure": sections.get("Metadata", ""),
        "DataProcedure": sections.get("Data", ""),
        "EpilogProcedure": sections.get("Epilog", ""),
        "DataSource": {"Type": "None"},
        "Parameters": parameters,
        "Variables": [],
        "VariablesUIData": [],
        "Attributes": {"Caption": process_name}
    }
    return payload

# Example usage:
file_path = "test.pro"
process_name = "test"

sections, parameters = parse_ti_file(file_path)
paw_json = build_paw_json(process_name, sections, parameters)

# Export to JSON file
with open(f"{process_name}_paw.json", "w") as f:
    json.dump(paw_json, f, indent=2)

print("PAW JSON generated successfully!")

