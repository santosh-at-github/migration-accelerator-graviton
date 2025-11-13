import psutil
import json
import re
import subprocess
import shlex

def load_json(filename):
    with open(filename, encoding='utf-8') as f:
        return [item.get('pname' if filename == 'isv1.json' else 'name') for item in json.load(f)]

def get_process_versions(process_names):
    versions = []
    for name in process_names:
        try:
            safe_name = shlex.quote(name)
            # Validate process name to prevent injection
            if not safe_name.replace('-', '').replace('_', '').isalnum():
                versions.append(f"Invalid process name: {safe_name}")
                continue
            output = subprocess.check_output([safe_name, '-v'], text=True, timeout=5)
            versions.append(output.strip())
        except subprocess.CalledProcessError:
            versions.append(f"Version info not available for {safe_name}")
    return versions

# Load known ISV and system process names
known_isv = load_json('isv1.json')
sys = load_json('sys.json')
userip = load_json('userip.json')

#append the user and known_isv
json_files = ['isv1.json', 'userip.json']
python_objects = []

for json_file in json_files:
    with open(json_file, "r", encoding='utf-8') as f:
        python_objects.append(json.load(f))

#create a new json file to compare with 
with open('combined_isv.json', 'w', encoding='utf-8') as f:
    json.dump(python_objects, f, indent=4)

#read the combined_isv file
combined_isv = load_json('combined_isv.json')

# Identify present and unknown ISV processes
present = [process.name() for process in psutil.process_iter() if process.name() in combined_isv]
unknown_isv = [process.name() for process in psutil.process_iter() if process.name() not in known_isv]

# Filter out known system processes and 'kworker/' processes
unknown = [process for process in set(unknown_isv) - set(sys) if not re.match('kworker/', process)]

# Get versions of present ISV processes
present_versions = get_process_versions(present)

# Output results
print("These are present on the server:", present)
if present:
    print("The versions present on the server are:", present_versions)
print("These are unaccounted for:", unknown)
print("Please reach out to the Graviton team for more assistance.")