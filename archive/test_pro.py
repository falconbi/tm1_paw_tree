import os
from tm1_connect import get_session

# Relative path from the script to the .pro file
file_path = './bedrock/main/}bedrock.cube.data.copy.pro'

# Connect to TM1
session = get_session()

# Make a TM1-safe process name
process_name = os.path.basename(file_path).replace('.pro', '').replace('}', '_')

# Read the .pro file content
with open(file_path, 'r') as f:
    pro_content = f.read()

# Simple payload: put everything in DataProcedure
payload = {
    'Name': process_name,
    'PrologProcedure': '',
    'MetadataProcedure': '',
    'DataProcedure': pro_content
}

# REST API URL for this process
url = f"{session.base_url}/Processes('{process_name}')"

# Upload the process
response = session.put(url, json=payload)

if response.status_code in (200, 201):
    print(f"Uploaded successfully: {process_name}")
else:
    print(f"Failed to upload: {process_name} - {response.status_code} {response.text}")

