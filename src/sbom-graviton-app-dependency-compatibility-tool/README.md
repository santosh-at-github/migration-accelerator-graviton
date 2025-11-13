# SBOM Graviton App Dependency Compatibility Tool

A tool for analyzing Java application dependencies for compatibility with ARM architecture (AWS Graviton).

## Overview

This tool helps developers and architects assess the compatibility of their Java applications with ARM-based processors like AWS Graviton. It analyzes dependencies from various sources (pom.xml files, SBOM files, JAR files) to identify potential compatibility issues when migrating from x86 to ARM architecture.

## Features

- Analyze Maven dependencies from pom.xml files
- Process Software Bill of Materials (SBOM) files in CycloneDX or SPDX formats
- Scan JAR files for native code and architecture-specific libraries
- Detect dependencies with known ARM compatibility issues
- Identify dependencies with potential endianness or memory alignment concerns
- Check for ARM-specific classifiers in Maven Central
- Generate detailed compatibility reports
- Perform runtime testing on ARM architecture (optional)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/sbom-graviton-app-dependency-compatibility-tool.git
cd sbom-graviton-app-dependency-compatibility-tool
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

Analyze a pom.xml file:
```bash
# generate effective pom.xml from your codebase
mvn help:effective-pom -Doutput=effective-pom.xml
python java_arm_compatibility.py path/to/effective-pom.xml
```

Analyze an SBOM file:
```bash
python java_arm_compatibility.py path/to/sbom.json
```

### Advanced Options

Perform deep scanning of JAR files:
```bash
python java_arm_compatibility.py path/to/pom.xml --deep-scan
```

Perform runtime testing (requires ARM architecture):
```bash
python java_arm_compatibility.py path/to/pom.xml --runtime-test
```

## Output

The tool generates:

1. A summary of compatibility issues in the console
2. An Excel file with detailed analysis results
3. A Markdown report with comprehensive compatibility information

## Understanding the Results

The analysis categorizes dependencies as:

- **Compatible**: No known issues running on ARM
- **Incompatible**: Known issues with ARM architecture
- **Native Code**: Contains native libraries that may need ARM-specific builds
- **Endianness Issues**: May have problems with byte ordering on ARM
- **Memory Alignment Issues**: May have problems with memory alignment on ARM

## Compatibility Guide

For a comprehensive guide on Java application compatibility with ARM architecture, see [Java ARM Compatibility Guide](java_arm_compatibility_guide.md).

## Dependencies

- Python 3.6+
- pandas
- requests
- Maven (for runtime testing)
- Java JDK (for JAR analysis)


## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- AWS Graviton team for their documentation on ARM compatibility
- CycloneDX and SPDX communities for SBOM standards
- Maven community for dependency management tools