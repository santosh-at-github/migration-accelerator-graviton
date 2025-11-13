# Graviton Migration Tools

This repository contains two scripts to help developers validate and migrate their applications to AWS Graviton (ARM64) architecture:
- `graviton-migration.sh`: Base Image validation to tell us if this can be moved to ARM.
- `graviton-ai-migration.sh`: Base Image validation with AI-assisted Dockerfile recommendation

## Prerequisites

- Linux/Unix environment
- sudo privileges
- Internet connection

The scripts will automatically install the following dependencies if not present:
- Git
- Docker
- Skopeo
- jq

## graviton-migration.sh

### Description
A script that analyzes Docker containers for ARM64 compatibility and attempts to build them for AWS Graviton.

### Features
- Validates Docker base images for ARM64 support
- Automatically attempts ARM64 builds
- Supports repositories with multiple Dockerfiles
- Provides colored output for better visibility

### Usage
```bash
./graviton-migration.sh
# Enter your repository URL when prompted


## graviton-ai-migration.sh
### Description
An AI-enhanced version of the migration tool that provides deeper analysis and intelligent recommendations for Graviton migration.

### Features

All features from graviton-migration.sh

AI-powered Dockerfile analysis

Smart recommendations for fixing the dockerfile

### Usage
./graviton-ai-migration.sh
# Enter your repository URL when prompted


Example output:

Checking required dependencies...
✓ Git is already installed
✓ Docker is already installed
✓ Skopeo is already installed

Scanning for Dockerfiles...
→ Checking base image: python:3.9-slim
→ Inspecting image for ARM64 support...
✓ python:3.9-slim supports ARM64

### Contributing
Feel free to submit issues and enhancement requests!