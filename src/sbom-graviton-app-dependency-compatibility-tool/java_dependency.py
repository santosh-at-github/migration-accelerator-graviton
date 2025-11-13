import os
import json
import requests
import time
import subprocess
import defusedxml.ElementTree as ET
import shutil
from pathlib import Path

def read_json_file(file_path):
    """Read and parse JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data



def is_private_dependency(component):
    """
    Determine if a dependency is private by checking if it exists in Maven Central.
    Returns True if the dependency is private (not found in Maven Central).
    """
    if 'purl' not in component:
        return True
    
    name = component.get('name', '')
    version = component.get('version', '')
    
    if not name or not version or ':' not in name:
        return True
    
    group_id, artifact_id = name.split(':', 1)
    
    # Maven Central REST API URL
    base_url = "https://search.maven.org/solrsearch/select"
    
    try:
        # Construct the query to search for exact match
        query = f'g:"{group_id}" AND a:"{artifact_id}" AND v:"{version}"'
        params = {
            'q': query,
            'rows': 1,
            'wt': 'json'
        }
        
        # Add retry mechanism with exponential backoff
        max_retries = 3
        retry_delay = 1  # Initial delay in seconds
        
        for attempt in range(max_retries):
            try:
                response = requests.get(base_url, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                # If numFound is 0, the artifact is not in Maven Central
                return data['response']['numFound'] == 0
                
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    # Log error on final attempt
                    print(f"Error checking Maven Central for {name}:{version}: {str(e)}")
                    return True  # Assume private if we can't verify
                
                # Wait before retrying with exponential backoff
                retry_delay *= 2
                
    except Exception as e:
        # Log any unexpected errors
        print(f"Unexpected error checking dependency {name}:{version}: {str(e)}")
        return True  # Assume private if we encounter any errors

def get_maven_coordinates(component):
    """Extract Maven coordinates from a component."""
    # Only process components of type "library"
    if component.get('type') != 'library' or 'purl' not in component:
        return None
    
    purl = component['purl']
    name = component.get('name', '')
    version = component.get('version', '')
    
    # Extract scope from purl
    scope = None
    if 'scope=' in purl:
        scope_part = purl.split('scope=')[1]
        scope = scope_part.split('&')[0] if '&' in scope_part else scope_part
    
    # Extract type from purl (default to 'jar' if not specified)
    dependency_type = 'jar'
    if 'type=' in purl:
        type_part = purl.split('type=')[1]
        dependency_type = type_part.split('&')[0] if '&' in type_part else type_part
    # For import scope, the type should be 'pom'
    elif scope == 'import':
        dependency_type = 'pom'
    
    # Extract groupId and artifactId from name
    if ':' in name:
        group_id, artifact_id = name.split(':', 1)
    else:
        return None
        
    return {
        'groupId': group_id,
        'artifactId': artifact_id,
        'version': version,
        'scope': scope,
        'type': dependency_type
    }

def generate_dependency_xml(dep, indent='    '):
    """Generate Maven dependency XML."""
    xml = f"""{indent}<dependency>
{indent}    <groupId>{dep['groupId']}</groupId>
{indent}    <artifactId>{dep['artifactId']}</artifactId>
{indent}    <version>{dep['version']}</version>"""
    
    # Add type if it's not the default 'jar'
    if dep.get('type') and dep['type'] != 'jar':
        xml += f"\n{indent}    <type>{dep['type']}</type>"
    
    # Add scope if present
    if dep.get('scope'):
        xml += f"\n{indent}    <scope>{dep['scope']}</scope>"
        
    xml += f"\n{indent}</dependency>"
    return xml

def generate_parent_xml(dep, indent='  '):
    """Generate Maven parent XML."""
    xml = f"""{indent}<parent>
{indent}    <groupId>{dep['groupId']}</groupId>
{indent}    <artifactId>{dep['artifactId']}</artifactId>
{indent}    <version>{dep['version']}</version>
{indent}</parent>"""
    return xml


def ensure_directory_exists(directory_path):
    """Ensure that the specified directory exists, creating it if necessary."""
    Path(directory_path).mkdir(parents=True, exist_ok=True)

def extract_dependencies_from_pom(pom_path):
    """Extract individual dependencies from a pom.xml file."""
    try:
        # Parse the XML file
        tree = ET.parse(pom_path)
        root = tree.getroot()
        
        # Define namespace
        ns = {'maven': 'http://maven.apache.org/POM/4.0.0'}
        
        # Extract dependencies
        dependencies = []
        
        # Get regular dependencies
        for dep in root.findall('.//maven:dependencies/maven:dependency', ns):
            group_id = dep.find('./maven:groupId', ns).text
            artifact_id = dep.find('./maven:artifactId', ns).text
            version = dep.find('./maven:version', ns).text
            
            # Get scope if it exists
            scope_elem = dep.find('./maven:scope', ns)
            scope = scope_elem.text if scope_elem is not None else None
            
            # Get type if it exists
            type_elem = dep.find('./maven:type', ns)
            dep_type = type_elem.text if type_elem is not None else 'jar'
            
            dependencies.append({
                'groupId': group_id,
                'artifactId': artifact_id,
                'version': version,
                'scope': scope,
                'type': dep_type
            })
        
        return dependencies
    except Exception as e:
        print(f"Error extracting dependencies from pom.xml: {str(e)}")
        return []

def create_temp_pom_for_dependency(dep, base_pom_path, temp_pom_path):
    """Create a temporary pom.xml with just one dependency."""
    try:
        # Create a new minimal POM file with just the single dependency
        pom_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">

    <modelVersion>4.0.0</modelVersion>
    
    <groupId>com.amazon.graviton-compatibility</groupId>
    <artifactId>dependency-test</artifactId>
    <version>1.0</version>
    
    <dependencies>
        <dependency>
            <groupId>{dep['groupId']}</groupId>
            <artifactId>{dep['artifactId']}</artifactId>
            <version>{dep['version']}</version>"""
        
        # Add type if it's not the default 'jar'
        if dep.get('type') and dep['type'] != 'jar':
            pom_content += f"\n            <type>{dep['type']}</type>"
        
        # Add scope if present
        if dep.get('scope'):
            pom_content += f"\n            <scope>{dep['scope']}</scope>"
            
        pom_content += """
        </dependency>
    </dependencies>
</project>
"""
        
        # Write the content to the temporary file
        with open(temp_pom_path, 'w', encoding='utf-8') as f:
            f.write(pom_content)
            
        return True
    except Exception as e:
        print(f"Error creating temporary pom.xml for {dep['groupId']}:{dep['artifactId']}: {str(e)}")
        return False

def run_maven_install(pom_path):
    """Run Maven install on the specified pom.xml file."""
    try:
        print(f"Running Maven install on {pom_path}...")
        result = subprocess.run(['mvn', 'install', '-f', pom_path], 
                               capture_output=True, text=True, check=False)
        
        if result.returncode == 0:
            print(f"Maven install successful for {pom_path}")
            return True, result.stdout
        else:
            print(f"Maven install failed for {pom_path}")
            print(f"Error: {result.stderr}")
            return False, result.stderr
    except Exception as e:
        print(f"Error running Maven install: {str(e)}")
        return False, str(e)

def install_dependencies_individually(pom_path, errors_file_path):
    """Install dependencies one by one and track failures."""
    # Ensure the directory for errors.txt exists
    ensure_directory_exists(os.path.dirname(errors_file_path))
    
    # Extract dependencies from pom.xml
    dependencies = extract_dependencies_from_pom(pom_path)
    
    if not dependencies:
        print("No dependencies found in pom.xml")
        return 0, 0
    
    # Create a temporary directory for individual pom files
    temp_dir = os.path.join(os.path.dirname(pom_path), 'temp_poms')
    ensure_directory_exists(temp_dir)
    
    # Track success and failure counts
    success_count = 0
    failure_count = 0
    failed_deps = []
    
    try:
        # Process each dependency
        for dep in dependencies:
            dep_id = f"{dep['groupId']}:{dep['artifactId']}:{dep['version']}"
            print(f"\nInstalling dependency: {dep_id}")
            
            # Create a temporary pom.xml for this dependency
            temp_pom_path = os.path.join(temp_dir, f"{dep['artifactId']}_pom.xml")
            if create_temp_pom_for_dependency(dep, pom_path, temp_pom_path):
                # Run Maven install on this dependency
                success, output = run_maven_install(temp_pom_path)
                
                if success:
                    success_count += 1
                else:
                    failure_count += 1
                    failed_deps.append({
                        'dependency': dep_id,
                        'error': output
                    })
        
        # Write failed dependencies to errors.txt
        if failed_deps:
            with open(errors_file_path, 'w', encoding='utf-8') as f:
                f.write(f"Failed dependencies: {failure_count}\n\n")
                for failed_dep in failed_deps:
                    f.write(f"Dependency: {failed_dep['dependency']}\n")
                    f.write(f"Error: {failed_dep['error']}\n")
                    f.write("-" * 80 + "\n\n")
            print(f"\nFailed dependencies written to {errors_file_path}")
    
    finally:
        # Clean up temporary directory
        try:
            shutil.rmtree(temp_dir)
            print(f"Temporary directory {temp_dir} cleaned up.")
        except Exception as e:
            print(f"Error cleaning up temporary directory: {str(e)}")
    
    print(f"\nDependency installation summary:")
    print(f"  - Total dependencies: {len(dependencies)}")
    print(f"  - Successfully installed: {success_count}")
    print(f"  - Failed to install: {failure_count}")
    
    return success_count, failure_count

def dependency_validate(file_path, type):
    """Process SBOM file and generate pom.xml with dependencies."""
    data = read_json_file(file_path)
    
    if type.lower() != 'maven':
        raise ValueError(f"Unsupported dependency type: {type}")
    
    public_deps = []
    private_deps = []
    import_deps = []  # List for import scope dependencies
    parent_deps = []  # List for parent dependencies (with -parent suffix)
    
    # Process components
    seen_artifacts = set()  # To track unique dependencies
    
    for component in data.get('components', []):
        coords = get_maven_coordinates(component)
        if coords is None:
            continue
            
        # Create unique identifier
        artifact_id = f"{coords['groupId']}:{coords['artifactId']}"
        if artifact_id in seen_artifacts:
            continue
        seen_artifacts.add(artifact_id)
        
        # Check if this is a parent dependency (artifactId ends with -parent or is spring-boot-starter-parent)
        if coords['artifactId'].endswith('-parent') or coords['artifactId'] == 'spring-boot-starter-parent':
            parent_deps.append(coords)
        # Check if this is an import scope dependency
        elif coords.get('scope') == 'import':
            import_deps.append(coords)
        elif is_private_dependency(component):
            private_deps.append(coords)
        else:
            public_deps.append(coords)
    
    # Generate pom.xml content
    pom_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"   
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"  
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0   
         http://maven.apache.org/xsd/maven-4.0.0.xsd">  
  
  <modelVersion>4.0.0</modelVersion>  
  
  <groupId>com.amazon.graviton-compatibility</groupId>  
  <artifactId>{os.path.basename(os.path.splitext(file_path)[0])}</artifactId>  
  <version>1.0</version>  
  
  <packaging>jar</packaging>
  <name>Maven Dependencies from SBOM</name>  
  """
    
    # Add parent section if there are parent dependencies
    if parent_deps:
        # Only use the first parent dependency as Maven only supports one parent
        pom_content += f"\n{generate_parent_xml(parent_deps[0])}\n"
        
        # If there are multiple parent dependencies, add a comment about the limitation
        if len(parent_deps) > 1:
            pom_content += "\n  <!-- Note: Maven only supports one parent. Additional parent dependencies are ignored. -->\n"
    
    # Add dependencyManagement section if there are import scope dependencies
    if import_deps:
        pom_content += """
  <dependencyManagement>
    <dependencies>
"""
        # Add import scope dependencies to dependencyManagement
        for dep in import_deps:
            pom_content += f"\n{generate_dependency_xml(dep)}\n"
            
        pom_content += "    </dependencies>\n  </dependencyManagement>\n"
    
    # Add regular dependencies section
    pom_content += """
  <dependencies>
"""
    
    # Add public dependencies (excluding those that were added as parent)
    for dep in public_deps:
        pom_content += f"\n{generate_dependency_xml(dep)}\n"
    
    # Add private dependencies as comments
    if private_deps:
        pom_content += "\n    <!-- Private/Internal Dependencies -->\n"
        for dep in private_deps:
            dep_xml = generate_dependency_xml(dep)
            commented_lines = [f"    <!-- {line} -->" for line in dep_xml.split('\n')]
            pom_content += '\n'.join(commented_lines) + '\n'
    
    pom_content += "  </dependencies>\n</project>\n"
    
    # Write to pom.xml
    pom_path = './assets/java/pom.xml'
    ensure_directory_exists(os.path.dirname(pom_path))
    with open(pom_path, 'w', encoding='utf-8') as f:
        f.write(pom_content)
    
    print(f"Generated pom.xml with {len(public_deps)} public, {len(private_deps)} private, {len(import_deps)} import, and {len(parent_deps)} parent dependencies")
    
    # Install dependencies individually and track failures
    errors_file_path = './assets/java/errors.txt'
    success_count, failure_count = install_dependencies_individually(pom_path, errors_file_path)
    
    return {
        'public_dependencies': len(public_deps),
        'private_dependencies': len(private_deps),
        'import_dependencies': len(import_deps),
        'parent_dependencies': len(parent_deps),
        'successful_installs': success_count,
        'failed_installs': failure_count
    }

if __name__ == '__main__':
    result = dependency_validate('./assets/java/sample-app-sbom.json', 'Maven')
    print(f"Generated pom.xml with {result['public_dependencies']} public, {result['private_dependencies']} private, {result['import_dependencies']} import, and {result['parent_dependencies']} parent dependencies")
    print(f"Successfully installed {result['successful_installs']} dependencies, {result['failed_installs']} failed")