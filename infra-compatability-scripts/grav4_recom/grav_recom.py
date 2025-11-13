import json
import math

# Constants for memory conversion
MEMORY_CONVERSION_FACTOR = 1024 * 1024  # Convert kB to GB

# Function to get total memory in GB
def get_total_memory():
    try:
        # Read /proc/meminfo directly instead of using subprocess
        with open('/proc/meminfo', 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('MemTotal:'):
                    mem_total_kb = int(line.split()[1])
                    return math.ceil(mem_total_kb / MEMORY_CONVERSION_FACTOR)
        return 0
    except Exception as e:
        print(f"Error retrieving memory: {e}")
        return 0

# Load the JSON file with the Graviton specs
def load_graviton_specs(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error loading JSON file: {e}")
        return None

# Main logic to find suitable Graviton instance
def find_suitable_graviton_instance(data, mem_total):
    grav_instance = None
    vcpu = 0

    for entry in data:
        memory_dict = entry['memory']
        vcpu_dict = entry['cpu']

        # Check for suitable memory types
        for key, value in memory_dict.items():
            key_as_int = int(key)
            if key_as_int >= mem_total:
                grav_instance = value
                mem_total = key_as_int  # Update mem_total to match the found key
                vcpu = vcpu_dict.get(grav_instance, 0)
                break  # Exit the loop once a suitable instance is found
        if grav_instance:  # Break the outer loop if we found an instance
            break

    return grav_instance, mem_total, vcpu

# Main execution
mem_total = get_total_memory()
graviton_data = load_graviton_specs('grav4.json')

if graviton_data:
    grav_instance, mem_total, vcpu = find_suitable_graviton_instance(graviton_data, mem_total)

    if grav_instance:
        print(f"The Graviton Instance Recommended: {grav_instance}")
        print(f"The Graviton Instance Memory: {mem_total} GB")
        print(f"The Graviton Instance VCPU: {vcpu}")
    else:
        print("No suitable Graviton instance found.")
else:
    print("Failed to retrieve Graviton specifications.")