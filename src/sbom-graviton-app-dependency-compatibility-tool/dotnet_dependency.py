import pandas as pd
import sys
import subprocess
import os
import re
import datetime
import json
import tempfile
import shutil

def read_json_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def create_temp_csproj(packages):
    """Create a temporary .csproj file for Graviton compatibility testing."""
    csproj_content = '''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net6.0</TargetFramework>
    <RuntimeIdentifier>linux-arm64</RuntimeIdentifier>
  </PropertyGroup>
  <ItemGroup>
'''
    for package in packages:
        csproj_content += f'    <PackageReference Include="{package["name"]}" Version="{package["version"]}" />\n'
    
    csproj_content += '''  </ItemGroup>
</Project>'''
    return csproj_content

def dependency_validate(data_file, type):
    data = read_json_file(data_file)
    components = data['components']
    
    # Create DataFrame
    df = pd.DataFrame()
    df["Component"] = ""
    df["Version"] = ""
    df["Compatible on Graviton?"] = ""
    df["Log Snippet"] = ""
    df["Timestamp"] = ""
    
    # Extract .NET/NuGet packages
    dotnet_packages = []
    for component in components:
        if component.get('purl', '').startswith('pkg:nuget/'):
            dotnet_packages.append({
                'name': component['name'],
                'version': component['version']
            })
    
    if not dotnet_packages:
        print("No .NET/NuGet packages found in SBOM")
        return df
    
    print(f"Found {len(dotnet_packages)} .NET packages to validate for Graviton compatibility")
    
    # Create temporary directory for testing
    temp_dir = tempfile.mkdtemp()
    csproj_path = os.path.join(temp_dir, 'test.csproj')
    
    try:
        # Test packages in batches to optimize performance
        batch_size = 10
        for i in range(0, len(dotnet_packages), batch_size):
            batch = dotnet_packages[i:i+batch_size]
            
            # Create .csproj with current batch
            csproj_content = create_temp_csproj(batch)
            with open(csproj_path, 'w', encoding='utf-8') as f:
                f.write(csproj_content)
            
            # Test batch restore for Graviton
            try:
                command_output = subprocess.check_output(
                    ['dotnet', 'restore', csproj_path, '--runtime', 'linux-arm64'],
                    stderr=subprocess.STDOUT,
                    cwd=temp_dir,
                    text=True
                )
                batch_success = True
                batch_error = ""
            except subprocess.CalledProcessError as e:
                batch_success = False
                batch_error = e.output
                command_output = e.output
            
            # Test individual packages in batch
            for pkg in batch:
                row_idx = len(df)
                df.at[row_idx, 'Component'] = pkg['name']
                df.at[row_idx, 'Version'] = pkg['version']
                df.at[row_idx, 'Timestamp'] = datetime.datetime.now()
                
                if batch_success:
                    # Individual package test
                    individual_csproj = create_temp_csproj([pkg])
                    with open(csproj_path, 'w', encoding='utf-8') as f:
                        f.write(individual_csproj)
                    
                    try:
                        individual_output = subprocess.check_output(
                            ['dotnet', 'restore', csproj_path, '--runtime', 'linux-arm64'],
                            stderr=subprocess.STDOUT,
                            cwd=temp_dir,
                            text=True
                        )
                        df.at[row_idx, 'Compatible on Graviton?'] = 'Yes'
                        df.at[row_idx, 'Log Snippet'] = 'Package restored successfully for Graviton'
                        print(f"✓ {pkg['name']}@{pkg['version']} - Graviton Compatible")
                    except subprocess.CalledProcessError as e:
                        df.at[row_idx, 'Compatible on Graviton?'] = 'No'
                        df.at[row_idx, 'Log Snippet'] = e.output
                        print(f"✗ {pkg['name']}@{pkg['version']} - Graviton Incompatible")
                else:
                    # Check if specific package caused batch failure
                    if pkg['name'].lower() in batch_error.lower():
                        df.at[row_idx, 'Compatible on Graviton?'] = 'No'
                        df.at[row_idx, 'Log Snippet'] = batch_error
                        print(f"✗ {pkg['name']}@{pkg['version']} - Graviton Incompatible")
                    else:
                        df.at[row_idx, 'Compatible on Graviton?'] = 'Unknown'
                        df.at[row_idx, 'Log Snippet'] = 'Batch restore failed, individual test needed'
                        print(f"? {pkg['name']}@{pkg['version']} - Graviton Compatibility Unknown")
    
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    return df