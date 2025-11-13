import distro
import json

#optimised code for the dynamic json file

dist_name = distro.name()
dist_version = distro.version()
dist = f"{dist_name} {dist_version}"

with open('os.json', encoding='utf-8') as f:
    data = json.load(f)
    file_version = [version for item in data if item['name'] == dist_name for version in item['versions']]

print(dist)
print("This operating system version is compatible with Graviton" if dist_version in file_version else "This operating system version is not compatible with Graviton")