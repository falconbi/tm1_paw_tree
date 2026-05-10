import json
from tm1_connect import get_session

process_name = "test"

session = get_session()
url = f"{session.base_url}/Processes('{process_name}')"
response = session.get(url)

if response.status_code == 200:
    ti_json = response.json()
    with open(f"{process_name}_export.json", "w") as f:
        json.dump(ti_json, f, indent=4)
    print(f"Process '{process_name}' exported to {process_name}_export.json")
else:
    print(f"Failed to export process '{process_name}': {response.status_code}")
    print(response.text)

