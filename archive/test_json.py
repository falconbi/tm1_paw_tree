import json
from tm1_connect import tm1  # use your existing connection

# Load the test JSON file
with open("test_export.JSON", "r") as f:
    process_json = json.load(f)

# Try to create or update the process in TM1
try:
    tm1.processes.create(process_json)
    print("Process loaded successfully!")
except Exception as e:
    print("Error loading process:", e)

