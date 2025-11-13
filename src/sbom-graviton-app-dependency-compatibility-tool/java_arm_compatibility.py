#!/usr/bin/env python3
"""
Java ARM Compatibility Analyzer

This script analyzes Java dependencies for compatibility with ARM architecture (AWS Graviton).
It identifies dependencies with native code that might have issues running on ARM.

The analyzer examines:
1. POM.xml files for direct and transitive dependencies
2. Software Bill of Materials (SBOM) files for comprehensive dependency analysis
3. JAR files for native libraries and architecture-specific code
4. Maven classifiers and dependency scopes that indicate architecture-specific requirements
"""

import os
import sys
import json
import requests
import subprocess
import defusedxml.ElementTree as ET
import shutil
import pandas as pd
import re
import tempfile
import argparse
import time
from pathlib import Path
import zipfile
from collections import defaultdict

# Add the project root to the path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import java_dependency

# Known libraries with ARM compatibility issues
KNOWN_PROBLEMATIC_LIBRARIES = {
    'com.github.jnr:jnr-ffi': {
        'issue': 'Native code compatibility issues with ARM',
        'fixed_in': '2.2.0',
        'recommendation': 'Upgrade to version 2.2.0 or later',
        'details': 'Uses native code for FFI that requires ARM-specific builds'
    },
    'net.java.dev.jna:jna': {
        'issue': 'Native code compatibility issues with ARM',
        'fixed_in': '5.5.0',
        'recommendation': 'Upgrade to version 5.5.0 or later',
        'details': 'JNA provides Java access to native libraries, requires ARM-compatible native components'
    },
    'org.xerial:sqlite-jdbc': {
        'issue': 'Native code compatibility issues with ARM',
        'fixed_in': '3.34.0',
        'recommendation': 'Upgrade to version 3.34.0 or later',
        'details': 'Contains native SQLite libraries that need ARM-specific builds'
    },
    'io.netty:netty-transport-native-epoll': {
        'issue': 'Native code compatibility issues with ARM',
        'fixed_in': '4.1.46.Final',
        'recommendation': 'Upgrade to version 4.1.46.Final or later',
        'details': 'Uses native epoll libraries that require ARM-specific builds'
    },
    'org.rocksdb:rocksdbjni': {
        'issue': 'Native code compatibility issues with ARM',
        'fixed_in': '6.15.2',
        'recommendation': 'Upgrade to version 6.15.2 or later',
        'details': 'RocksDB JNI bindings require ARM-compatible native libraries'
    },
    'org.lwjgl:lwjgl': {
        'issue': 'Native code compatibility issues with ARM',
        'fixed_in': '3.3.0',
        'recommendation': 'Upgrade to version 3.3.0 or later',
        'details': 'Lightweight Java Game Library uses native code that needs ARM support'
    },
    'com.github.luben:zstd-jni': {
        'issue': 'Native code compatibility issues with ARM',
        'fixed_in': '1.5.0-4',
        'recommendation': 'Upgrade to version 1.5.0-4 or later',
        'details': 'JNI bindings to Zstandard compression library require ARM-compatible builds'
    },
    'org.lz4:lz4-java': {
        'issue': 'Native code compatibility issues with ARM',
        'fixed_in': '1.8.0',
        'recommendation': 'Upgrade to version 1.8.0 or later',
        'details': 'LZ4 compression algorithm implementation with JNI bindings needs ARM support'
    },
    'org.apache.hadoop:hadoop-native': {
        'issue': 'Native code compatibility issues with ARM',
        'fixed_in': '3.3.0',
        'recommendation': 'Upgrade to version 3.3.0 or later',
        'details': 'Hadoop native libraries need ARM-specific builds'
    },
    'io.netty:netty-transport-native-unix-common': {
        'issue': 'Native code compatibility issues with ARM',
        'fixed_in': '4.1.46.Final',
        'recommendation': 'Upgrade to version 4.1.46.Final or later',
        'details': 'Unix-specific native transport libraries need ARM support'
    },
    'org.apache.arrow:arrow-vector': {
        'issue': 'Native code compatibility issues with ARM',
        'fixed_in': '5.0.0',
        'recommendation': 'Upgrade to version 5.0.0 or later',
        'details': 'Arrow memory management uses native code that needs ARM support'
    },
    'org.bytedeco:javacpp': {
        'issue': 'Native code compatibility issues with ARM',
        'fixed_in': '1.5.5',
        'recommendation': 'Upgrade to version 1.5.5 or later',
        'details': 'JavaCPP provides native C++ integration that requires ARM-specific builds'
    }
}

# Libraries known to contain native code
NATIVE_CODE_LIBRARIES = [
    'org.lwjgl',
    'com.github.jnr',
    'net.java.dev.jna',
    'org.xerial',
    'io.netty',
    'org.rocksdb',
    'org.bytedeco',
    'org.apache.hadoop:hadoop-common',
    'org.apache.hadoop:hadoop-hdfs',
    'org.apache.hadoop:hadoop-native',
    'org.apache.spark',
    'org.tensorflow',
    'org.apache.tinkerpop:gremlin-driver',
    'com.sun.jna',
    'org.eclipse.swt',
    'org.fusesource',
    'com.github.luben:zstd-jni',
    'org.lz4:lz4-java',
    'org.apache.arrow',
    'io.netty:netty-transport-native',
    'org.hdrhistogram:HdrHistogram',
    'com.github.oshi:oshi-core',
    'org.apache.commons:commons-crypto',
    'org.apache.commons:commons-compress',
    'org.apache.lucene:lucene-core',
    'org.eclipse.jetty:jetty-native',
    'com.github.jbellis:jamm',
    'org.lmdbjava:lmdbjava',
    'org.neo4j:neo4j-native',
    'org.apache.cassandra:cassandra-all',
    'native-lib-loader'
]

# Libraries that may have endianness issues
ENDIANNESS_SENSITIVE_LIBRARIES = [
    'java.nio.ByteBuffer',
    'org.apache.hadoop:hadoop-common',
    'org.apache.arrow',
    'org.xerial:sqlite-jdbc',
    'org.rocksdb:rocksdbjni',
    'org.lmdbjava:lmdbjava',
    'org.apache.commons:commons-compress',
    'org.apache.lucene:lucene-core'
]

# Libraries that may have memory alignment issues
MEMORY_ALIGNMENT_SENSITIVE_LIBRARIES = [
    'sun.misc.Unsafe',
    'jdk.internal.misc.Unsafe',
    'org.apache.arrow',
    'org.bytedeco:javacpp',
    'org.rocksdb:rocksdbjni',
    'org.lmdbjava:lmdbjava',
    'org.apache.hadoop:hadoop-common'
]

# Libraries with known ARM-specific classifiers
ARM_CLASSIFIER_LIBRARIES = {
    'io.netty:netty-transport-native-epoll': ['linux-aarch_64', 'linux-arm_64'],
    'org.lwjgl:lwjgl': ['natives-linux-arm64', 'natives-linux-arm32'],
    'org.bytedeco:javacpp': ['linux-arm64', 'linux-armhf'],
    'org.xerial:sqlite-jdbc': ['linux-aarch64', 'linux-arm'],
    'org.rocksdb:rocksdbjni': ['linux-aarch64', 'linux-arm64'],
    'com.github.luben:zstd-jni': ['linux-aarch64', 'linux-arm64'],
    'org.lz4:lz4-java': ['linux-aarch64', 'linux-arm64']
}

def compare_versions(version1, version2):
    """
    Compare two version strings.
    Returns:
    - negative if version1 < version2
    - zero if version1 == version2
    - positive if version1 > version2
    """
    def normalize(v):
        # Handle special cases like 'Final', 'RELEASE', etc.
        v = v.lower()
        if 'final' in v:
            v = v.replace('final', '')
        if 'release' in v:
            v = v.replace('release', '')
        return v.strip()
    
    # Split version parts and normalize
    parts1 = [normalize(p) for p in re.split(r'[\.\-]', version1)]
    parts2 = [normalize(p) for p in re.split(r'[\.\-]', version2)]
    
    # Compare each part
    for i in range(max(len(parts1), len(parts2))):
        if i >= len(parts1):
            return -1  # version1 is shorter, so it's older
        if i >= len(parts2):
            return 1   # version2 is shorter, so version1 is newer
        
        # Try numeric comparison first
        try:
            v1 = int(parts1[i])
            v2 = int(parts2[i])
            if v1 != v2:
                return v1 - v2
        except ValueError:
            # If not numeric, compare as strings
            if parts1[i] != parts2[i]:
                return -1 if parts1[i] < parts2[i] else 1
    
    return 0  # Versions are equal

def check_jar_for_native_code(jar_path):
    """
    Check if a JAR file contains native code (.so, .dll, .dylib files).
    Returns a dictionary with information about native libraries found.
    """
    try:
        native_libs = {
            'has_native_code': False,
            'native_files': [],
            'arm_specific': False,
            'x86_specific': False,
            'platform_dirs': set(),
            'native_lib_loaders': False
        }
        
        # Try using zipfile first (more reliable cross-platform)
        try:
            with zipfile.ZipFile(jar_path, 'r') as jar:
                jar_contents = jar.namelist()
        except:
            # Fall back to jar command if zipfile fails
            result = subprocess.run(['jar', 'tf', jar_path], 
                                  capture_output=True, text=True, check=False)
            
            if result.returncode != 0:
                print(f"Error examining JAR file {jar_path}: {result.stderr}")
                return native_libs
            
            jar_contents = result.stdout.splitlines()
        
        # Check for native library files and platform-specific directories
        for entry in jar_contents:
            # Check for native libraries
            if entry.endswith('.so') or entry.endswith('.dll') or entry.endswith('.dylib'):
                native_libs['has_native_code'] = True
                native_libs['native_files'].append(entry)
                
                # Check for ARM-specific libraries
                if any(arm_arch in entry.lower() for arm_arch in 
                      ['arm64', 'aarch64', 'arm', 'aarch32', 'armv7', 'armv8']):
                    native_libs['arm_specific'] = True
                
                # Check for x86-specific libraries
                if any(x86_arch in entry.lower() for x86_arch in 
                      ['x86_64', 'x86', 'amd64', 'i386', 'i686']):
                    native_libs['x86_specific'] = True
            
            # Check for platform-specific directories
            platform_dirs = [
                'linux-arm', 'linux-arm64', 'linux-aarch64', 'linux-x86', 'linux-x86_64', 'linux-amd64',
                'windows-arm', 'windows-arm64', 'windows-x86', 'windows-x86_64', 'windows-amd64',
                'darwin-arm64', 'darwin-x86_64', 'darwin-amd64',
                'lib/arm', 'lib/arm64', 'lib/aarch64', 'lib/x86', 'lib/x86_64', 'lib/amd64',
                'META-INF/native'
            ]
            
            for platform_dir in platform_dirs:
                if platform_dir in entry:
                    native_libs['has_native_code'] = True
                    native_libs['platform_dirs'].add(platform_dir)
                    
                    if any(arm_dir in platform_dir.lower() for arm_dir in ['arm', 'aarch']):
                        native_libs['arm_specific'] = True
                    
                    if any(x86_dir in platform_dir.lower() for x86_dir in ['x86', 'amd64', 'i386', 'i686']):
                        native_libs['x86_specific'] = True
            
            # Check for native library loaders
            if 'native-lib-loader' in entry or 'NativeLibraryLoader' in entry:
                native_libs['native_lib_loaders'] = True
        
        # Convert platform_dirs set to list for JSON serialization
        native_libs['platform_dirs'] = list(native_libs['platform_dirs'])
        
        return native_libs
    
    except Exception as e:
        print(f"Error checking JAR for native code: {str(e)}")
        return {
            'has_native_code': False,
            'native_files': [],
            'arm_specific': False,
            'x86_specific': False,
            'platform_dirs': [],
            'native_lib_loaders': False,
            'error': str(e)
        }

def check_dependency_arm_compatibility(dep):
    """
    Check if a dependency is compatible with ARM architecture.
    Returns a dict with compatibility information.
    """
    group_id = dep['groupId']
    artifact_id = dep['artifactId']
    version = dep['version']
    scope = dep.get('scope', 'compile')
    dep_type = dep.get('type', 'jar')
    classifier = dep.get('classifier', '')
    
    dep_key = f"{group_id}:{artifact_id}"
    
    result = {
        'groupId': group_id,
        'artifactId': artifact_id,
        'version': version,
        'scope': scope,
        'type': dep_type,
        'classifier': classifier,
        'hasNativeCode': False,
        'isCompatible': True,
        'issue': None,
        'recommendation': None,
        'details': None,
        'hasArmSpecificBuild': False,
        'endiannessIssues': False,
        'memoryAlignmentIssues': False
    }
    
    # Check if this dependency has an ARM-specific classifier
    if classifier and any(arm_arch in classifier.lower() for arm_arch in 
                         ['arm64', 'aarch64', 'arm', 'aarch32', 'armv7', 'armv8']):
        result['hasArmSpecificBuild'] = True
        result['isCompatible'] = True
        result['issue'] = "Using ARM-specific classifier"
        result['recommendation'] = "No action needed, already using ARM-specific build"
    
    # Check if this is a known problematic library
    if dep_key in KNOWN_PROBLEMATIC_LIBRARIES:
        issue_info = KNOWN_PROBLEMATIC_LIBRARIES[dep_key]
        result['hasNativeCode'] = True
        result['details'] = issue_info.get('details')
        
        # Check if the current version is older than the fixed version
        if compare_versions(version, issue_info['fixed_in']) < 0:
            result['isCompatible'] = False
            result['issue'] = issue_info['issue']
            result['recommendation'] = issue_info['recommendation']
        else:
            result['issue'] = f"Previously had {issue_info['issue']}, but fixed in this version"
    
    # Check if this library is known to contain native code
    for native_lib in NATIVE_CODE_LIBRARIES:
        if dep_key.startswith(native_lib):
            result['hasNativeCode'] = True
            if not result['issue']:  # Only set if not already set
                result['issue'] = "Contains native code that may need ARM-specific builds"
                result['recommendation'] = "Test thoroughly on ARM architecture"
    
    # Check if this library is known to have ARM-specific classifiers available
    if dep_key in ARM_CLASSIFIER_LIBRARIES:
        available_classifiers = ARM_CLASSIFIER_LIBRARIES[dep_key]
        if not classifier or not any(arm_classifier in classifier for arm_classifier in available_classifiers):
            if result['isCompatible']:  # Only suggest if not already marked incompatible
                result['recommendation'] = f"Consider using an ARM-specific classifier: {', '.join(available_classifiers)}"
    
    # Check for endianness issues
    for endianness_lib in ENDIANNESS_SENSITIVE_LIBRARIES:
        if dep_key.startswith(endianness_lib):
            result['endiannessIssues'] = True
            if not result['issue'] or "endianness" not in result['issue'].lower():
                current_issue = result['issue'] or ""
                result['issue'] = f"{current_issue}{',' if current_issue else ''} Potential endianness issues on ARM"
                current_rec = result['recommendation'] or ""
                result['recommendation'] = f"{current_rec}{',' if current_rec else ''} Test byte order handling on ARM"
    
    # Check for memory alignment issues
    for alignment_lib in MEMORY_ALIGNMENT_SENSITIVE_LIBRARIES:
        if dep_key.startswith(alignment_lib):
            result['memoryAlignmentIssues'] = True
            if not result['issue'] or "alignment" not in result['issue'].lower():
                current_issue = result['issue'] or ""
                result['issue'] = f"{current_issue}{',' if current_issue else ''} Potential memory alignment issues on ARM"
                current_rec = result['recommendation'] or ""
                result['recommendation'] = f"{current_rec}{',' if current_rec else ''} Test memory access patterns on ARM"
    
    # If we haven't identified any issues but the library has native code,
    # we should still flag it for testing
    if result['hasNativeCode'] and result['isCompatible'] and not result['issue']:
        result['issue'] = "Contains native code that may need ARM-specific builds"
        result['recommendation'] = "Test thoroughly on ARM architecture"
    
    # Clean up any leading/trailing commas in issue and recommendation
    if result['issue']:
        result['issue'] = result['issue'].strip().strip(',').strip()
    if result['recommendation']:
        result['recommendation'] = result['recommendation'].strip().strip(',').strip()
    
    return result

def test_dependency_on_arm(dep, temp_dir, debug=True):
    """
    Test a dependency on ARM architecture by creating a simple test project.
    Returns True if the dependency works on ARM, False otherwise.
    
    Note: This function should be run on an ARM machine (like AWS Graviton).
    """
    # Check if we're running on ARM
    is_arm = False
    try:
        arch = subprocess.run(['uname', '-m'], capture_output=True, text=True).stdout.strip()
        is_arm = arch in ['aarch64', 'arm64']
    except:
        # On Windows, try a different approach
        try:
            arch = subprocess.run(['wmic', 'os', 'get', 'OSArchitecture'], capture_output=True, text=True).stdout
            is_arm = 'ARM' in arch
        except:
            print("Could not determine system architecture")
    
    if not is_arm:
        print("Warning: Not running on ARM architecture. Test results may not be accurate.")
    
    # Create a simple test project
    test_project_dir = os.path.join(temp_dir, f"test-{dep['artifactId']}")
    os.makedirs(test_project_dir, exist_ok=True)
    
    # Create a simple Java class that uses the dependency
    test_class = f"""
package com.amazon.gravitontest;

import java.io.File;
import java.io.IOException;
import java.net.URI;
import java.net.URISyntaxException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Enumeration;
import java.util.jar.JarEntry;
import java.util.jar.JarFile;

public class DependencyTest {{
    public static void main(String[] args) {{
        System.out.println("Testing {dep['groupId']}:{dep['artifactId']}:{dep['version']}");
        try {{
            // Simple check - if we got this far, Maven resolved the dependency
            System.out.println("Maven successfully resolved the dependency");
            
            // Try to find the JAR file in the Maven repository
            String jarPath = System.getProperty("user.home") + 
                "/.m2/repository/{dep['groupId'].replace('.', '/')}/{dep['artifactId']}/{dep['version']}/" +
                "{dep['artifactId']}-{dep['version']}.jar";
            
            File jarFile = new File(jarPath);
            if (jarFile.exists()) {{
                System.out.println("Found dependency JAR: " + jarPath);
                
                // Try to load a class from the JAR
                try {{
                    JarFile jar = new JarFile(jarFile);
                    Enumeration<JarEntry> entries = jar.entries();
                    
                    // Find first class file and try to load it
                    while (entries.hasMoreElements()) {{
                        JarEntry entry = entries.nextElement();
                        String name = entry.getName();
                        
                        if (name.endsWith(".class")) {{
                            // Convert path to class name
                            String className = name.replace('/', '.').substring(0, name.length() - 6);
                            if (!className.contains("$")) {{ // Skip inner classes
                                System.out.println("Attempting to load class: " + className);
                                try {{
                                    Class.forName(className);
                                    System.out.println("Successfully loaded class from dependency");
                                    break;
                                }} catch (ClassNotFoundException cnfe) {{
                                    System.out.println("Class not found: " + className + " (this is normal)");
                                    // Continue to next class
                                }}
                            }}
                        }}
                    }}
                    jar.close();
                }} catch (Exception e) {{
                    System.out.println("Warning: Could not inspect JAR: " + e.getMessage());
                    // Continue execution - this is just a warning
                }}
            }} else {{
                System.out.println("JAR file not found at expected location, but Maven resolved it");
            }}
            
            // Test passed if we got this far without exception
            System.out.println("Dependency test completed successfully");
            
        }} catch (Exception e) {{
            System.out.println("Error testing dependency: " + e.getMessage());
            e.printStackTrace();
            System.exit(1);
        }}
    }}
}}
"""
    
    # Create a pom.xml for the test project
    test_pom = f"""<?xml version="1.0" encoding="UTF-8"?>
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
            <version>{dep['version']}</version>
        </dependency>
    </dependencies>
    
    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>3.8.1</version>
                <configuration>
                    <source>1.8</source>
                    <target>1.8</target>
                </configuration>
            </plugin>
            <plugin>
                <groupId>org.codehaus.mojo</groupId>
                <artifactId>exec-maven-plugin</artifactId>
                <version>3.0.0</version>
                <configuration>
                    <mainClass>com.amazon.gravitontest.DependencyTest</mainClass>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
"""
    
    # Create directory structure for package
    package_dir = os.path.join(test_project_dir, "src", "main", "java", "com", "amazon", "gravitontest")
    os.makedirs(package_dir, exist_ok=True)
    
    # Write the files
    with open(os.path.join(test_project_dir, "pom.xml"), "w", encoding='utf-8') as f:
        f.write(test_pom)
    
    with open(os.path.join(package_dir, "DependencyTest.java"), "w", encoding='utf-8') as f:
        f.write(test_class)
    
    # Try to compile and run the test
    try:
        # Compile with debug output
        compile_result = subprocess.run(['mvn', 'compile', '-X'], 
                                      cwd=test_project_dir,
                                      capture_output=True, text=True, check=False)
        
        if compile_result.returncode != 0:
            print(f"Compilation failed: \n{compile_result.stderr}\nStdout: {compile_result.stdout}")
            return False, f"{compile_result.stderr}\n{compile_result.stdout}"
        
        # Run with verbose output
        run_result = subprocess.run(['mvn', 'exec:java', '-X'], 
                                   cwd=test_project_dir,
                                   capture_output=True, text=True, check=False)
        
        if run_result.returncode != 0:
            print(f"Execution failed: \n{run_result.stderr}\nStdout: {run_result.stdout}")
            return False, f"{run_result.stderr}\n{run_result.stdout}"
        
        return True, run_result.stdout
    
    except Exception as e:
        print(f"Error testing dependency: {str(e)}")
        return False, str(e)

def analyze_pom_file(pom_path, deep_scan=False, runtime_test=False):
    """
    Analyze a pom.xml file for ARM compatibility issues.
    Returns a DataFrame with compatibility information.
    
    Parameters:
    - pom_path: Path to the pom.xml file
    - deep_scan: If True, scan JAR files for native code
    - runtime_test: If True, perform runtime testing on ARM
    """
    print(f"Analyzing pom.xml at {pom_path}...")
    
    # Check for Maven plugins and configurations related to ARM
    arm_plugin_configs = check_pom_for_arm_plugins(pom_path)
    if arm_plugin_configs:
        print("\nFound Maven plugins with ARM-specific configurations:")
        for config in arm_plugin_configs:
            print(f"  - {config}")
    
    # Check for dependency management section
    dependency_management = check_pom_for_dependency_management(pom_path)
    if dependency_management:
        print(f"\nFound {len(dependency_management)} dependencies in dependencyManagement section")
    
    # Extract dependencies from pom.xml
    dependencies = java_dependency.extract_dependencies_from_pom(pom_path)
    
    if not dependencies:
        print("No dependencies found in pom.xml")
        return pd.DataFrame()
    
    print(f"Found {len(dependencies)} dependencies to analyze")
    
    # Create a temporary directory for testing if needed
    temp_dir = None
    if runtime_test:
        temp_dir = tempfile.mkdtemp()

    # Install dependencies individually
    print("\nInstalling dependencies individually...")
    errors_file_path = os.path.join(os.path.dirname(pom_path), 'errors.txt')
    success_count, failure_count = java_dependency.install_dependencies_individually(pom_path, errors_file_path)
    print(f"Successfully installed {success_count} dependencies, {failure_count} failed")
    
    try:
        # Check each dependency for ARM compatibility
        compatibility_results = []
        for dep in dependencies:
            print(f"Checking {dep['groupId']}:{dep['artifactId']}:{dep['version']}...")
            compatibility_info = check_dependency_arm_compatibility(dep)
            
            # If deep scan is enabled, try to find and check the JAR file
            if deep_scan:
                # Try to find the JAR file in the local Maven repository
                jar_path = os.path.expanduser(f"~/.m2/repository/{dep['groupId'].replace('.', '/')}/{dep['artifactId']}/{dep['version']}/{dep['artifactId']}-{dep['version']}.jar")
                
                # Check for classifier in the path if present
                if 'classifier' in dep and dep['classifier']:
                    jar_path = os.path.expanduser(f"~/.m2/repository/{dep['groupId'].replace('.', '/')}/{dep['artifactId']}/{dep['version']}/{dep['artifactId']}-{dep['version']}-{dep['classifier']}.jar")
                
                if os.path.exists(jar_path):
                    print(f"  Performing deep scan of JAR file: {jar_path}")
                    native_code_info = check_jar_for_native_code(jar_path)
                    
                    if native_code_info['has_native_code']:
                        compatibility_info['hasNativeCode'] = True
                        
                        # Update compatibility info based on JAR analysis
                        if native_code_info['arm_specific'] and not native_code_info['x86_specific']:
                            compatibility_info['hasArmSpecificBuild'] = True
                            compatibility_info['issue'] = "Contains ARM-specific native libraries"
                            compatibility_info['recommendation'] = "No action needed for ARM compatibility"
                        elif native_code_info['x86_specific'] and not native_code_info['arm_specific']:
                            compatibility_info['isCompatible'] = False
                            compatibility_info['issue'] = "Contains x86-specific native libraries without ARM equivalents"
                            compatibility_info['recommendation'] = "Look for an ARM-compatible version or alternative library"
                        elif native_code_info['arm_specific'] and native_code_info['x86_specific']:
                            compatibility_info['hasArmSpecificBuild'] = True
                            compatibility_info['issue'] = "Contains both ARM and x86 native libraries"
                            compatibility_info['recommendation'] = "Test thoroughly on ARM architecture"
                        else:
                            compatibility_info['issue'] = "Native code detected in JAR file"
                            compatibility_info['recommendation'] = "Test thoroughly on ARM architecture"
                        
                        # Add details about native libraries found
                        if native_code_info['native_files']:
                            compatibility_info['details'] = f"Native libraries found: {', '.join(native_code_info['native_files'][:5])}"
                            if len(native_code_info['native_files']) > 5:
                                compatibility_info['details'] += f" and {len(native_code_info['native_files']) - 5} more"
                        
                        # Check for native library loaders
                        if native_code_info['native_lib_loaders']:
                            compatibility_info['details'] = (compatibility_info.get('details', '') + 
                                                           " Uses native library loader, which may need configuration for ARM.")
                else:
                    print(f"  JAR file not found in local repository: {jar_path}")
                    
                    # Try to check Maven Central for ARM-specific classifiers
                    arm_classifiers = check_maven_central_for_arm_classifiers(dep)
                    if arm_classifiers:
                        print(f"  Found ARM-specific classifiers in Maven Central: {', '.join(arm_classifiers)}")
                        compatibility_info['recommendation'] = f"Consider using one of these ARM-specific classifiers: {', '.join(arm_classifiers)}"
            
            # If runtime testing is enabled and the dependency has native code, test it
            if runtime_test and compatibility_info['hasNativeCode'] and temp_dir:
                print(f"  Performing runtime test for {dep['groupId']}:{dep['artifactId']}...")
                success, output = test_dependency_on_arm(dep, temp_dir, debug=True)
                if not success:
                    compatibility_info['isCompatible'] = False
                    compatibility_info['issue'] = "Failed runtime test on ARM"
                    compatibility_info['recommendation'] = "Check error output and consider upgrading"
                    print(f"  Runtime test failed: {output}")
                else:
                    print(f"  Runtime test passed")
            
            compatibility_results.append(compatibility_info)
    
    finally:
        # Clean up temporary directory if it was created
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    # Convert results to DataFrame
    df = pd.DataFrame(compatibility_results)
    
    # Add a column for overall recommendation
    if not df.empty:
        df['overallRecommendation'] = df.apply(
            lambda row: row['recommendation'] if not row['isCompatible'] else (
                row['recommendation'] if row['hasNativeCode'] else "No action needed"
            ),
            axis=1
        )
    
    # Save results to Excel
    output_dir = './arm_compatibility_results'
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    output_path = os.path.join(output_dir, 'arm_compatibility_results.xlsx')
    df.to_excel(output_path, index=False)
    print(f"ARM compatibility analysis saved to {output_path}")
    
    # Generate a detailed report
    report_path = os.path.join(output_dir, 'arm_compatibility_report.md')
    generate_compatibility_report(df, report_path, "POM XML", [])
    print(f"Detailed compatibility report saved to {report_path}")
    
    # Summary statistics
    if not df.empty:
        total_deps = len(df)
        compatible_deps = len(df[df['isCompatible']])
        native_code_deps = len(df[df['hasNativeCode']])
        incompatible_deps = len(df[~df['isCompatible']])
        endianness_issues = len(df[df['endiannessIssues']]) if 'endiannessIssues' in df.columns else 0
        alignment_issues = len(df[df['memoryAlignmentIssues']]) if 'memoryAlignmentIssues' in df.columns else 0
        arm_specific_builds = len(df[df['hasArmSpecificBuild']]) if 'hasArmSpecificBuild' in df.columns else 0
        
        print(f"\nARM Compatibility Summary:")
        print(f"  - Total dependencies: {total_deps}")
        print(f"  - Compatible dependencies: {compatible_deps} ({compatible_deps/total_deps*100:.1f}%)")
        print(f"  - Dependencies with native code: {native_code_deps} ({native_code_deps/total_deps*100:.1f}%)")
        print(f"  - Dependencies with ARM-specific builds: {arm_specific_builds} ({arm_specific_builds/total_deps*100:.1f}%)")
        print(f"  - Dependencies with potential endianness issues: {endianness_issues} ({endianness_issues/total_deps*100:.1f}%)")
        print(f"  - Dependencies with potential memory alignment issues: {alignment_issues} ({alignment_issues/total_deps*100:.1f}%)")
        print(f"  - Incompatible dependencies: {incompatible_deps} ({incompatible_deps/total_deps*100:.1f}%)")
        
        # Print incompatible dependencies
        if incompatible_deps > 0:
            print("\nIncompatible dependencies that need attention:")
            incompatible_df = df[~df['isCompatible']]
            for _, row in incompatible_df.iterrows():
                print(f"  - {row['groupId']}:{row['artifactId']}:{row['version']}")
                print(f"    Issue: {row['issue']}")
                print(f"    Recommendation: {row['recommendation']}")
                if 'details' in row and row['details']:
                    print(f"    Details: {row['details']}")
    
    return df

def check_pom_for_arm_plugins(pom_path):
    """
    Check a pom.xml file for Maven plugins with ARM-specific configurations.
    Returns a list of plugin configurations related to ARM.
    """
    arm_configs = []
    try:
        # Parse the XML file
        tree = ET.parse(pom_path)
        root = tree.getroot()
        
        # Define namespace
        ns = {'maven': 'http://maven.apache.org/POM/4.0.0'}
        
        # Check for Spring Boot Maven plugin with imagePlatform configuration
        spring_boot_plugins = root.findall('.//maven:plugin[maven:artifactId="spring-boot-maven-plugin"]', ns)
        for plugin in spring_boot_plugins:
            image_platform_elements = plugin.findall('.//maven:imagePlatform', ns)
            for platform_elem in image_platform_elements:
                if platform_elem is not None and 'arm' in platform_elem.text.lower():
                    arm_configs.append(f"Spring Boot Maven Plugin with imagePlatform={platform_elem.text}")
        
        # Check for Docker Maven plugin with platform configuration
        docker_plugins = root.findall('.//maven:plugin[maven:artifactId="docker-maven-plugin"]', ns)
        for plugin in docker_plugins:
            platform_elements = plugin.findall('.//maven:platform', ns)
            for platform_elem in platform_elements:
                if platform_elem is not None and 'arm' in platform_elem.text.lower():
                    arm_configs.append(f"Docker Maven Plugin with platform={platform_elem.text}")
        
        # Check for Jib Maven plugin with platform configuration
        jib_plugins = root.findall('.//maven:plugin[maven:artifactId="jib-maven-plugin"]', ns)
        for plugin in jib_plugins:
            platform_elements = plugin.findall('.//maven:platform', ns)
            for platform_elem in platform_elements:
                if platform_elem is not None and 'arm' in platform_elem.text.lower():
                    arm_configs.append(f"Jib Maven Plugin with platform={platform_elem.text}")
        
        # Check for Maven Compiler plugin with ARM-specific configurations
        compiler_plugins = root.findall('.//maven:plugin[maven:artifactId="maven-compiler-plugin"]', ns)
        for plugin in compiler_plugins:
            arg_elements = plugin.findall('.//maven:arg', ns)
            for arg_elem in arg_elements:
                if arg_elem is not None and 'arm' in arg_elem.text.lower():
                    arm_configs.append(f"Maven Compiler Plugin with ARM-specific argument: {arg_elem.text}")
        
        # Check for Maven Surefire plugin with ARM-specific configurations
        surefire_plugins = root.findall('.//maven:plugin[maven:artifactId="maven-surefire-plugin"]', ns)
        for plugin in surefire_plugins:
            arg_elements = plugin.findall('.//maven:argLine', ns)
            for arg_elem in arg_elements:
                if arg_elem is not None and ('arm' in arg_elem.text.lower() or 'arch' in arg_elem.text.lower()):
                    arm_configs.append(f"Maven Surefire Plugin with architecture-specific argument: {arg_elem.text}")
        
        return arm_configs
    except Exception as e:
        print(f"Error checking POM for ARM plugins: {str(e)}")
        return []

def check_pom_for_dependency_management(pom_path):
    """
    Check a pom.xml file for dependency management section.
    Returns a list of dependencies in the dependencyManagement section.
    """
    managed_deps = []
    try:
        # Parse the XML file
        tree = ET.parse(pom_path)
        root = tree.getroot()
        
        # Define namespace
        ns = {'maven': 'http://maven.apache.org/POM/4.0.0'}
        
        # Get dependencies in dependencyManagement section
        for dep in root.findall('.//maven:dependencyManagement/maven:dependencies/maven:dependency', ns):
            group_id = dep.find('./maven:groupId', ns).text
            artifact_id = dep.find('./maven:artifactId', ns).text
            version = dep.find('./maven:version', ns).text
            
            # Get scope if it exists
            scope_elem = dep.find('./maven:scope', ns)
            scope = scope_elem.text if scope_elem is not None else None
            
            # Get type if it exists
            type_elem = dep.find('./maven:type', ns)
            dep_type = type_elem.text if type_elem is not None else 'jar'
            
            # Get classifier if it exists
            classifier_elem = dep.find('./maven:classifier', ns)
            classifier = classifier_elem.text if classifier_elem is not None else None
            
            managed_deps.append({
                'groupId': group_id,
                'artifactId': artifact_id,
                'version': version,
                'scope': scope,
                'type': dep_type,
                'classifier': classifier
            })
        
        return managed_deps
    except Exception as e:
        print(f"Error checking POM for dependency management: {str(e)}")
        return []

def check_maven_central_for_arm_classifiers(dep):
    """
    Check Maven Central for ARM-specific classifiers for a dependency.
    Returns a list of available ARM-specific classifiers.
    """
    arm_classifiers = []
    try:
        group_id = dep['groupId']
        artifact_id = dep['artifactId']
        version = dep['version']
        
        # Maven Central REST API URL
        base_url = "https://search.maven.org/solrsearch/select"
        
        # Construct the query to search for the artifact
        query = f'g:"{group_id}" AND a:"{artifact_id}" AND v:"{version}"'
        params = {
            'q': query,
            'rows': 100,
            'wt': 'json'
        }
        
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Check for ARM-specific classifiers
        for doc in data.get('response', {}).get('docs', []):
            classifier = doc.get('c')
            if classifier and any(arm_arch in classifier.lower() for arm_arch in 
                               ['arm64', 'aarch64', 'arm', 'aarch32', 'armv7', 'armv8']):
                arm_classifiers.append(classifier)
        
        return arm_classifiers
    except Exception as e:
        print(f"Error checking Maven Central for ARM classifiers: {str(e)}")
        return []

def analyze_sbom_for_arm_compatibility(sbom_file_path, deep_scan=False, runtime_test=False):
    """
    Analyze a Software Bill of Materials (SBOM) file for ARM compatibility.
    Returns a DataFrame with compatibility information.
    
    Parameters:
    - sbom_file_path: Path to the SBOM JSON file
    - deep_scan: If True, scan JAR files for native code
    - runtime_test: If True, perform runtime testing on ARM
    """
    print(f"Processing SBOM file at {sbom_file_path}...")
    
    # Determine SBOM format (CycloneDX or SPDX)
    sbom_format = detect_sbom_format(sbom_file_path)
    print(f"Detected SBOM format: {sbom_format}")
    
    # Process SBOM file to generate pom.xml
    result = java_dependency.dependency_validate(sbom_file_path, 'maven')
    
    # Path to the generated pom.xml - use absolute path
    assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'java')
    pom_path = os.path.join(assets_dir, 'pom.xml')
    
    # Check if the SBOM contains any architecture-specific information
    arch_info = extract_architecture_info_from_sbom(sbom_file_path)
    if arch_info:
        print("\nArchitecture-specific information found in SBOM:")
        for item in arch_info:
            print(f"  - {item}")
    
    # Analyze dependencies for ARM compatibility
    df = analyze_pom_file(pom_path, deep_scan, runtime_test)
    
    # Save results to Excel
    output_dir = './arm_compatibility_results'
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    output_path = os.path.join(output_dir, 'arm_compatibility_results.xlsx')
    df.to_excel(output_path, index=False)
    print(f"ARM compatibility analysis saved to {output_path}")
    
    # Generate a detailed report
    report_path = os.path.join(output_dir, 'arm_compatibility_report.md')
    generate_compatibility_report(df, report_path, sbom_format, arch_info)
    print(f"Detailed compatibility report saved to {report_path}")
    
    # Summary statistics
    if not df.empty:
        total_deps = len(df)
        compatible_deps = len(df[df['isCompatible']])
        native_code_deps = len(df[df['hasNativeCode']])
        incompatible_deps = len(df[~df['isCompatible']])
        endianness_issues = len(df[df['endiannessIssues']]) if 'endiannessIssues' in df.columns else 0
        alignment_issues = len(df[df['memoryAlignmentIssues']]) if 'memoryAlignmentIssues' in df.columns else 0
        arm_specific_builds = len(df[df['hasArmSpecificBuild']]) if 'hasArmSpecificBuild' in df.columns else 0
        
        print(f"\nARM Compatibility Summary:")
        print(f"  - Total dependencies: {total_deps}")
        print(f"  - Compatible dependencies: {compatible_deps} ({compatible_deps/total_deps*100:.1f}%)")
        print(f"  - Dependencies with native code: {native_code_deps} ({native_code_deps/total_deps*100:.1f}%)")
        print(f"  - Dependencies with ARM-specific builds: {arm_specific_builds} ({arm_specific_builds/total_deps*100:.1f}%)")
        print(f"  - Dependencies with potential endianness issues: {endianness_issues} ({endianness_issues/total_deps*100:.1f}%)")
        print(f"  - Dependencies with potential memory alignment issues: {alignment_issues} ({alignment_issues/total_deps*100:.1f}%)")
        print(f"  - Incompatible dependencies: {incompatible_deps} ({incompatible_deps/total_deps*100:.1f}%)")
        
        # Print incompatible dependencies
        if incompatible_deps > 0:
            print("\nIncompatible dependencies that need attention:")
            incompatible_df = df[~df['isCompatible']]
            for _, row in incompatible_df.iterrows():
                print(f"  - {row['groupId']}:{row['artifactId']}:{row['version']}")
                print(f"    Issue: {row['issue']}")
                print(f"    Recommendation: {row['recommendation']}")
                if 'details' in row and row['details']:
                    print(f"    Details: {row['details']}")
    
    return df

def detect_sbom_format(sbom_file_path):
    """
    Detect the format of an SBOM file (CycloneDX or SPDX).
    """
    try:
        with open(sbom_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check for CycloneDX format
        if 'bomFormat' in data and data['bomFormat'] == 'CycloneDX':
            version = data.get('specVersion', 'unknown')
            return f"CycloneDX v{version}"
        
        # Check for SPDX format
        if 'spdxVersion' in data:
            version = data.get('spdxVersion', 'unknown')
            return f"SPDX {version}"
        
        # Check for other indicators
        if 'components' in data:
            return "CycloneDX (unspecified version)"
        if 'packages' in data:
            return "SPDX (unspecified version)"
        
        return "Unknown SBOM format"
    except Exception as e:
        print(f"Error detecting SBOM format: {str(e)}")
        return "Unknown (error parsing file)"

def extract_architecture_info_from_sbom(sbom_file_path):
    """
    Extract any architecture-specific information from an SBOM file.
    """
    arch_info = []
    try:
        with open(sbom_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Look for architecture information in CycloneDX format
        if 'components' in data:
            for component in data.get('components', []):
                # Check component properties
                properties = component.get('properties', [])
                for prop in properties:
                    if any(arch_term in prop.get('name', '').lower() for arch_term in 
                          ['arch', 'architecture', 'platform', 'cpu', 'processor']):
                        arch_info.append(f"Component {component.get('name')}: {prop.get('name')}={prop.get('value')}")
                
                # Check component name for architecture indicators
                name = component.get('name', '')
                if any(arch_term in name.lower() for arch_term in 
                      ['arm64', 'aarch64', 'arm', 'x86_64', 'amd64']):
                    arch_info.append(f"Component with architecture-specific name: {name}")
        
        # Look for architecture information in SPDX format
        if 'packages' in data:
            for package in data.get('packages', []):
                # Check package name and description for architecture indicators
                name = package.get('name', '')
                desc = package.get('description', '')
                
                if any(arch_term in name.lower() for arch_term in 
                      ['arm64', 'aarch64', 'arm', 'x86_64', 'amd64']):
                    arch_info.append(f"Package with architecture-specific name: {name}")
                
                if any(arch_term in desc.lower() for arch_term in 
                      ['arm64', 'aarch64', 'arm', 'x86_64', 'amd64', 'architecture', 'platform']):
                    arch_info.append(f"Package with architecture reference in description: {name}")
    
    except Exception as e:
        print(f"Error extracting architecture info from SBOM: {str(e)}")
    
    return arch_info

def generate_compatibility_report(df, report_path, sbom_format, arch_info):
    """
    Generate a detailed Markdown report of ARM compatibility analysis.
    """
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# Java Application ARM Compatibility Analysis\n\n")
            f.write(f"Analysis performed on {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## SBOM Information\n\n")
            f.write(f"- SBOM Format: {sbom_format}\n")
            
            if arch_info:
                f.write("\n### Architecture-Specific Information in SBOM\n\n")
                for item in arch_info:
                    f.write(f"- {item}\n")
            
            # Summary statistics
            if not df.empty:
                total_deps = len(df)
                compatible_deps = len(df[df['isCompatible']])
                native_code_deps = len(df[df['hasNativeCode']])
                incompatible_deps = len(df[~df['isCompatible']])
                endianness_issues = len(df[df['endiannessIssues']]) if 'endiannessIssues' in df.columns else 0
                alignment_issues = len(df[df['memoryAlignmentIssues']]) if 'memoryAlignmentIssues' in df.columns else 0
                arm_specific_builds = len(df[df['hasArmSpecificBuild']]) if 'hasArmSpecificBuild' in df.columns else 0
                
                f.write("\n## Compatibility Summary\n\n")
                f.write(f"- **Total dependencies**: {total_deps}\n")
                f.write(f"- **Compatible dependencies**: {compatible_deps} ({compatible_deps/total_deps*100:.1f}%)\n")
                f.write(f"- **Dependencies with native code**: {native_code_deps} ({native_code_deps/total_deps*100:.1f}%)\n")
                f.write(f"- **Dependencies with ARM-specific builds**: {arm_specific_builds} ({arm_specific_builds/total_deps*100:.1f}%)\n")
                f.write(f"- **Dependencies with potential endianness issues**: {endianness_issues} ({endianness_issues/total_deps*100:.1f}%)\n")
                f.write(f"- **Dependencies with potential memory alignment issues**: {alignment_issues} ({alignment_issues/total_deps*100:.1f}%)\n")
                f.write(f"- **Incompatible dependencies**: {incompatible_deps} ({incompatible_deps/total_deps*100:.1f}%)\n")
                
                # Incompatible dependencies
                if incompatible_deps > 0:
                    f.write("\n## Incompatible Dependencies\n\n")
                    incompatible_df = df[~df['isCompatible']]
                    for _, row in incompatible_df.iterrows():
                        f.write(f"### {row['groupId']}:{row['artifactId']}:{row['version']}\n\n")
                        f.write(f"- **Issue**: {row['issue']}\n")
                        f.write(f"- **Recommendation**: {row['recommendation']}\n")
                        if 'details' in row and row['details']:
                            f.write(f"- **Details**: {row['details']}\n")
                        f.write("\n")
                
                # Dependencies with native code
                if native_code_deps > 0:
                    f.write("\n## Dependencies with Native Code\n\n")
                    native_df = df[df['hasNativeCode']]
                    for _, row in native_df.iterrows():
                        f.write(f"### {row['groupId']}:{row['artifactId']}:{row['version']}\n\n")
                        f.write(f"- **Compatible**: {'Yes' if row['isCompatible'] else 'No'}\n")
                        if 'issue' in row and row['issue']:
                            f.write(f"- **Issue**: {row['issue']}\n")
                        if 'recommendation' in row and row['recommendation']:
                            f.write(f"- **Recommendation**: {row['recommendation']}\n")
                        if 'details' in row and row['details']:
                            f.write(f"- **Details**: {row['details']}\n")
                        f.write("\n")
                
                # Dependencies with endianness or memory alignment issues
                special_issues_df = df[(df['endiannessIssues'] | df['memoryAlignmentIssues']) 
                                      if ('endiannessIssues' in df.columns and 'memoryAlignmentIssues' in df.columns) 
                                      else pd.DataFrame()]
                
                if not special_issues_df.empty:
                    f.write("\n## Dependencies with Endianness or Memory Alignment Issues\n\n")
                    for _, row in special_issues_df.iterrows():
                        f.write(f"### {row['groupId']}:{row['artifactId']}:{row['version']}\n\n")
                        f.write(f"- **Endianness Issues**: {'Yes' if row['endiannessIssues'] else 'No'}\n")
                        f.write(f"- **Memory Alignment Issues**: {'Yes' if row['memoryAlignmentIssues'] else 'No'}\n")
                        if 'issue' in row and row['issue']:
                            f.write(f"- **Issue**: {row['issue']}\n")
                        if 'recommendation' in row and row['recommendation']:
                            f.write(f"- **Recommendation**: {row['recommendation']}\n")
                        f.write("\n")
                
                # All dependencies
                f.write("\n## All Dependencies\n\n")
                f.write("| Group ID | Artifact ID | Version | Compatible | Native Code | ARM Build | Issues |\n")
                f.write("|----------|------------|---------|------------|-------------|----------|--------|\n")
                
                for _, row in df.iterrows():
                    compatible = "✅" if row['isCompatible'] else "❌"
                    native_code = "✅" if row['hasNativeCode'] else "❌"
                    arm_build = "✅" if row.get('hasArmSpecificBuild', False) else "❌"
                    issues = row['issue'] if 'issue' in row and row['issue'] else "-"
                    
                    f.write(f"| {row['groupId']} | {row['artifactId']} | {row['version']} | {compatible} | {native_code} | {arm_build} | {issues} |\n")
            
            f.write("\n## Recommendations\n\n")
            f.write("### General Recommendations\n\n")
            f.write("1. **Update incompatible dependencies** to versions that support ARM architecture\n")
            f.write("2. **Test thoroughly on ARM hardware** or emulation, especially for dependencies with native code\n")
            f.write("3. **Use ARM-specific classifiers** when available for dependencies\n")
            f.write("4. **Be cautious with dependencies that manipulate binary data** due to potential endianness issues\n")
            f.write("5. **Check memory alignment requirements** for dependencies that use direct memory access\n")
            
            f.write("\n### Testing Recommendations\n\n")
            f.write("1. **Set up an ARM testing environment** using AWS Graviton instances or other ARM hardware\n")
            f.write("2. **Run comprehensive functional tests** to verify application behavior on ARM\n")
            f.write("3. **Perform performance testing** to identify any ARM-specific bottlenecks\n")
            f.write("4. **Use Java profiling tools** like JProfiler, VisualVM, or Java Flight Recorder on ARM\n")
            f.write("5. **Test with different JDK distributions** built for ARM (Amazon Corretto, Azul Zulu, Eclipse Temurin)\n")
            
            f.write("\n## References\n\n")
            f.write("- [AWS Graviton Documentation](https://aws.amazon.com/ec2/graviton/)\n")
            f.write("- [Java on ARM](https://www.azul.com/downloads/?package=jdk#download-openjdk)\n")
            f.write("- [Amazon Corretto](https://aws.amazon.com/corretto/)\n")
            f.write("- [Maven Documentation on Classifiers](https://maven.apache.org/pom.html#dependencies)\n")
            
    except Exception as e:
        print(f"Error generating compatibility report: {str(e)}")

def main():
    """Main function to run the ARM compatibility analyzer."""
    parser = argparse.ArgumentParser(description='Analyze Java dependencies for ARM compatibility')
    parser.add_argument('input_path', nargs='?', help='Path to pom.xml or SBOM JSON file')
    parser.add_argument('--deep-scan', action='store_true', help='Perform deep scanning of JAR files')
    parser.add_argument('--runtime-test', action='store_true', help='Perform runtime testing (requires ARM architecture)')
    args = parser.parse_args()
    
    # Check if deep scan is enabled
    if args.deep_scan:
        print("Deep scanning enabled - will check JAR files for native code")
    
    # Check if runtime testing is enabled
    if args.runtime_test:
        print("Runtime testing enabled - will test dependencies on ARM")
        
        # Check if we're running on ARM
        is_arm = False
        try:
            arch = subprocess.run(['uname', '-m'], capture_output=True, text=True).stdout.strip()
            is_arm = arch in ['aarch64', 'arm64']
        except:
            # On Windows, try a different approach
            try:
                arch = subprocess.run(['wmic', 'os', 'get', 'OSArchitecture'], capture_output=True, text=True).stdout
                is_arm = 'ARM' in arch
            except:
                print("Could not determine system architecture")
        
        if not is_arm:
            print("WARNING: Not running on ARM architecture. Runtime test results may not be accurate.")
    
    # Ensure assets directory exists
    assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'java')
    os.makedirs(assets_dir, exist_ok=True)
    
    if not args.input_path:
        # Default to sample SBOM if no arguments provided
        print("\nNo input file provided. Using default sample SBOM file...")
        sbom_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'java', 'sample-app-sbom.json')
        
        # Check if the default file exists
        if not os.path.exists(sbom_file_path):
            print(f"Default SBOM file not found at {sbom_file_path}")
            print("Please provide a path to a pom.xml or SBOM JSON file")
            return 1
        
        # Analyze the default SBOM file
        df = analyze_sbom_for_arm_compatibility(sbom_file_path, args.deep_scan, args.runtime_test)
    else:
        # Handle both absolute and relative paths
        if os.path.isabs(args.input_path):
            input_path = args.input_path
        else:
            # Convert relative path to absolute
            input_path = os.path.abspath(args.input_path)
        
        # Check if the file exists
        if not os.path.exists(input_path):
            print(f"File not found: {input_path}")
            print("Please provide a valid path to a pom.xml or SBOM JSON file")
            return 1
            
        # Determine if the input is a pom.xml or SBOM file
        if input_path.endswith('.xml'):
            df = analyze_pom_file(input_path, args.deep_scan, args.runtime_test)
        elif input_path.endswith('.json'):
            df = analyze_sbom_for_arm_compatibility(input_path, args.deep_scan, args.runtime_test)
        else:
            print(f"Unsupported file type: {input_path}")
            print("Please provide a pom.xml or SBOM JSON file")
            return 1
        
        if df.empty:
            print("No dependencies found to analyze")
            return 0
    
    return 0

if __name__ == '__main__':
    sys.exit(main())