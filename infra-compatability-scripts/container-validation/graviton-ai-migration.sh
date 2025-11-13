#!/bin/bash
# Define color codes
GREEN="\033[1;32m"
RED="\033[1;31m"
CYAN="\033[1;36m"
YELLOW="\033[1;33m"
BLUE="\033[1;34m"
RESET="\033[0m"

# GitHub repository to clone (pass as an argument)
read -p "Enter the repo URL of your App that contains Dockerfile: " REPO_URL
cd /tmp/

if [[ -z "$REPO_URL" ]]; then
    echo -e "${RED}No GitHub repository URL provided!${RESET}"
    echo "Usage: $0 <github-repo-url>"
    exit 1
fi

# Extract repo name from URL
REPO_NAME=$(basename -s .git "$REPO_URL")

# Function to install dependencies
install_dependencies() {
    echo -e "${CYAN}Checking required dependencies...${RESET}"

    # Install Git if not present
    if ! command -v git &>/dev/null; then
        echo -e "${RED}Git not found. Installing...${RESET}"
        sudo apt-get update && sudo apt-get install -y git || { echo -e "${RED} Failed to install Git. Exiting...${RESET}"; exit 1; }
    else
        echo -e "${GREEN} Git is already installed${RESET}"
    fi

    # Install Docker
    if ! command -v docker &>/dev/null; then
        echo -e "${RED}Docker not found. Installing...${RESET}"
        sudo apt-get update && sudo apt-get install -y docker.io || { echo -e "${RED} Failed to install Docker. Exiting...${RESET}"; exit 1; }
    else
        echo -e "${GREEN} Docker is already installed${RESET}"
    fi

    # Install Skopeo
    if ! command -v skopeo &>/dev/null; then
        echo -e "${RED}Skopeo not found. Installing...${RESET}"
        sudo apt-get update && sudo apt-get install -y skopeo || { echo -e "${RED} Failed to install Skopeo. Exiting...${RESET}"; exit 1; }
    else
        echo -e "${GREEN} Skopeo is already installed${RESET}"
    fi

    # Install jq if not present
    if ! command -v jq &>/dev/null; then
        echo -e "${RED}jq not found. Installing...${RESET}"
        sudo apt-get update && sudo apt-get install -y jq || { echo -e "${RED} Failed to install jq. Exiting...${RESET}"; exit 1; }
    else
        echo -e "${GREEN} jq is already installed${RESET}"
    fi

        # Check for Amazon Q CLI and install if not present
    if ! command -v q &>/dev/null; then
        echo -e "${YELLOW} Amazon Q CLI not found. Attempting to install...${RESET}"

        # Detect system architecture
        ARCH=$(uname -m)

        # Install Amazon Q CLI based on architecture
        if [[ "$ARCH" == "x86_64" ]]; then
            echo -e "${CYAN}Detected x86_64 architecture. Installing Amazon Q CLI...${RESET}"
            # Secure installation approach - download, verify, then execute
            TEMP_SCRIPT=$(mktemp)
            curl -fsSL https://d3f5l8t7vg6as8.cloudfront.net/x86_64/q-cli-installer.sh -o "$TEMP_SCRIPT" || {
                echo -e "${RED} Failed to download Amazon Q CLI installer.${RESET}"
                echo -e "${YELLOW} You can manually install from: https://aws.amazon.com/q/cli/${RESET}"
                echo -e "${YELLOW} Continuing without Amazon Q integration...${RESET}"
                rm -f "$TEMP_SCRIPT"
                USE_AMAZON_Q=false
                return
            }
            # Execute the downloaded script
            bash "$TEMP_SCRIPT" || {
                echo -e "${RED} Failed to install Amazon Q CLI.${RESET}"
                echo -e "${YELLOW} You can manually install from: https://aws.amazon.com/q/cli/${RESET}"
                echo -e "${YELLOW} Continuing without Amazon Q integration...${RESET}"
                USE_AMAZON_Q=false
            }
            rm -f "$TEMP_SCRIPT"
        elif [[ "$ARCH" == "aarch64" || "$ARCH" == "arm64" ]]; then
            echo -e "${CYAN}Detected ARM64 architecture. Installing Amazon Q CLI...${RESET}"
            # Secure installation approach - download, verify, then execute
            TEMP_SCRIPT=$(mktemp)
            curl -fsSL https://d3f5l8t7vg6as8.cloudfront.net/arm64/q-cli-installer.sh -o "$TEMP_SCRIPT" || {
                echo -e "${RED} Failed to download Amazon Q CLI installer.${RESET}"
                echo -e "${YELLOW} You can manually install from: https://aws.amazon.com/q/cli/${RESET}"
                echo -e "${YELLOW} Continuing without Amazon Q integration...${RESET}"
                rm -f "$TEMP_SCRIPT"
                USE_AMAZON_Q=false
                return
            }
            # Execute the downloaded script
            bash "$TEMP_SCRIPT" || {
                echo -e "${RED} Failed to install Amazon Q CLI.${RESET}"
                echo -e "${YELLOW} You can manually install from: https://aws.amazon.com/q/cli/${RESET}"
                echo -e "${YELLOW} Continuing without Amazon Q integration...${RESET}"
                USE_AMAZON_Q=false
            }
            rm -f "$TEMP_SCRIPT"
        else
            echo -e "${RED} Unsupported architecture: $ARCH${RESET}"
            echo -e "${YELLOW} Amazon Q CLI installation is only supported on x86_64 and arm64.${RESET}"
            echo -e "${YELLOW} Continuing without Amazon Q integration...${RESET}"
            USE_AMAZON_Q=false
            return
        fi

        # Verify installation
        if command -v q &>/dev/null; then
            echo -e "${GREEN} Amazon Q CLI installed successfully${RESET}"
            USE_AMAZON_Q=true
        else
            echo -e "${RED} Amazon Q CLI installation verification failed.${RESET}"
            echo -e "${YELLOW} Continuing without Amazon Q integration...${RESET}"
            USE_AMAZON_Q=false
        fi
    else
        echo -e "${GREEN} Amazon Q CLI is already installed${RESET}"
        USE_AMAZON_Q=true
    fi
}

# Function to analyze Dockerfile with Amazon Q
analyze_with_amazon_q() {
    local dockerfile=$1
    local requirements_file=$2

    if [[ "$USE_AMAZON_Q" == false ]]; then
        return
    fi

    echo -e "\n${BLUE}╔════════════════════════════════════════════════════════════╗${RESET}"
    echo -e "${BLUE}║                 AMAZON Q ANALYSIS                          ║${RESET}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${RESET}"

    # Create a temporary file for Q's analysis
    TEMP_FILE=$(mktemp)

    echo -e "${CYAN}Asking Amazon Q for ARM64 compatibility analysis...${RESET}"

    # Prepare the query for Amazon Q
    QUERY="Analyze this Dockerfile for ARM64 compatibility and suggest improvements:"

    # Add Dockerfile content to query
    echo -e $QUERY > $TEMP_FILE
    echo -e "Dockerfile content:\n$(cat $dockerfile)" >> $TEMP_FILE

    # Add requirements.txt content if it exists
    if [[ -f "$requirements_file" ]]; then
        echo -e "\nrequirements.txt content:\n$(cat $requirements_file)" >> $TEMP_FILE
    fi

    # Call Amazon Q CLI and capture the output
    echo -e "${YELLOW}Querying Amazon Q...${RESET}"
    q chat "$(cat $TEMP_FILE)" || {
        echo -e "${RED} Failed to get response from Amazon Q.${RESET}"
        rm $TEMP_FILE
        return 1
    }

    # Clean up
    rm $TEMP_FILE
}

# Function to check for requirements.txt and analyze Python dependencies
analyze_python_dependencies() {
    local dir=$(dirname "$1")
    local requirements_file="$dir/requirements.txt"

    if [[ -f "$requirements_file" ]]; then
        echo -e "${CYAN}Found requirements.txt. Analyzing Python dependencies...${RESET}"

        # Check for potentially problematic packages for ARM64
        local problematic_packages=("tensorflow<2.0" "torch<1.10" "opencv-python-headless<4.0" "numpy<1.19" "scipy<1.5" "pandas<1.0")
        local found_issues=false

        for package in "${problematic_packages[@]}"; do
            package_name=$(echo "$package" | cut -d '<' -f 1)
            if grep -q "$package_name" "$requirements_file"; then
                echo -e "${YELLOW} Potential ARM64 compatibility issue: $package_name${RESET}"
                echo -e "   Some older versions may not support ARM64 architecture."
                found_issues=true
            fi
        done

        if [[ "$found_issues" == false ]]; then
            echo -e "${GREEN} No obvious ARM64 compatibility issues found in Python dependencies${RESET}"
        else
            echo -e "${YELLOW} Recommendation: Check if newer versions of these packages support ARM64${RESET}"
        fi

        return 0
    fi

    return 1
}

# Function to check for multi-architecture support in Dockerfile
check_multiarch_support() {
    local dockerfile=$1

    if grep -q "platform=\$" "$dockerfile"; then
        echo -e "${GREEN} Dockerfile uses platform variables for multi-architecture support${RESET}"
    elif grep -q "BUILDPLATFORM\|TARGETPLATFORM" "$dockerfile"; then
        echo -e "${GREEN} Dockerfile uses BuildKit platform arguments for multi-architecture support${RESET}"
    else
        echo -e "${YELLOW} No explicit multi-architecture support found in Dockerfile${RESET}"
        echo -e "   Recommendation: Consider adding platform variables for better multi-arch support"
        echo -e "   Example: FROM --platform=\$TARGETPLATFORM base_image:tag"
    fi
}

# Function to check image architecture and build for ARM64
process_dockerfile() {
    local dockerfile=$1
    echo -e "${CYAN}Checking Dockerfile: $dockerfile${RESET}"

    # Check for multi-architecture support
    check_multiarch_support "$dockerfile"

    # Analyze Python dependencies if present
    local dir=$(dirname "$dockerfile")
    local requirements_file="$dir/requirements.txt"
    local has_requirements=false

    if analyze_python_dependencies "$dockerfile"; then
        has_requirements=true
    fi

    # Extract all base images (including multi-stage builds)
    BASE_IMAGES=$(grep -E '^FROM\s+' "$dockerfile" | sed -E 's/.*FROM\s+(--platform=[^ ]+ )?([^ ]+).*/\2/')

    if [[ -z "$BASE_IMAGES" ]]; then
        echo -e "${RED} No valid base image found in '$dockerfile'. Skipping...${RESET}"
        return 1
    fi

    # Check each base image
    local all_images_support_arm64=true

    while IFS= read -r BASE_IMAGE; do
        echo -e "→ Checking base image: ${CYAN}$BASE_IMAGE${RESET}"

        # Skip if the image is a build stage reference (FROM stage AS new-stage)
        if [[ "$BASE_IMAGE" == *" AS "* ]] || [[ "$BASE_IMAGE" == *" as "* ]]; then
            local stage_name=$(echo "$BASE_IMAGE" | awk '{print $1}')
            echo -e "${YELLOW} Skipping build stage reference: $stage_name${RESET}"
            continue
        fi

        # Check if image supports ARM64 using skopeo
        echo "→ Inspecting image for ARM64 support..."
        RAW_JSON=$(skopeo inspect --raw docker://"$BASE_IMAGE" 2>/dev/null)

        if [[ -z "$RAW_JSON" ]]; then
            echo -e "${RED} Unable to fetch details for $BASE_IMAGE.${RESET}"
            all_images_support_arm64=false
            continue
        fi

        # Check for ARM64 support in different manifest formats
        if echo "$RAW_JSON" | jq -e '.manifests' &>/dev/null; then
            # Multi-architecture image with manifest list
            if echo "$RAW_JSON" | jq -r '.manifests[].platform.architecture' 2>/dev/null | grep -q "arm64"; then
                echo -e "${GREEN} $BASE_IMAGE supports ARM64 via multi-arch manifest${RESET}"
            else
                echo -e "${RED} $BASE_IMAGE does NOT support ARM64 in its manifest list${RESET}"
                all_images_support_arm64=false
            fi
        elif echo "$RAW_JSON" | jq -e '.architecture' &>/dev/null; then
            # Single architecture image
            ARCH=$(echo "$RAW_JSON" | jq -r '.architecture')
            if [[ "$ARCH" == "arm64" ]]; then
                echo -e "${GREEN} $BASE_IMAGE is an ARM64 image${RESET}"
            else
                echo -e "${RED} $BASE_IMAGE is for $ARCH architecture, not ARM64${RESET}"
                all_images_support_arm64=false
            fi
        else
            echo -e "${RED} Could not determine architecture support for $BASE_IMAGE${RESET}"
            all_images_support_arm64=false
        fi
    done <<< "$BASE_IMAGES"

    # Use Amazon Q for advanced analysis
    if [[ "$USE_AMAZON_Q" == true ]]; then
        analyze_with_amazon_q "$dockerfile" "$requirements_file"
    fi

    # Attempt ARM64 build if all base images support it
    if [[ "$all_images_support_arm64" == true ]]; then
        echo ''
        echo -e "${CYAN}All base images support ARM64. Attempting to build $REPO_NAME on ARM64...${RESET}"
        sleep 2

        BUILD_TAG="$REPO_NAME:arm64-$(date +%s)"

        if docker build --platform linux/arm64 -t "$BUILD_TAG" -f "$dockerfile" . 1>/dev/null; then
            echo ''
            echo -e "${GREEN} Build successful for ARM64${RESET}"
            echo -e "${GREEN} Image tagged as: $BUILD_TAG${RESET}"
        else
            echo ''
            echo -e "${RED} Build failed for ARM64${RESET}"
            echo -e "${YELLOW} This could be due to architecture-specific code or dependencies in the application${RESET}"

            if [[ "$USE_AMAZON_Q" == true ]]; then
                echo -e "${CYAN}Asking Amazon Q for build failure analysis...${RESET}"
                q chat --no-interactive "The Docker build for ARM64 failed for this Dockerfile. What might be the issue and how can I fix it? Dockerfile content: $(cat $dockerfile)" 2>/dev/null
            fi

            return 1
        fi
    else
        echo ''
        echo -e "${RED} Not all base images support ARM64. Skipping build.${RESET}"
        echo -e "${YELLOW} Consider replacing base images with ARM64-compatible alternatives${RESET}"
        return 1
    fi
}

# Function to suggest ARM64 alternatives for common base images
# suggest_arm64_alternatives() {
#     echo -e "\n${CYAN}Suggestions for ARM64-compatible base images:${RESET}"
#     echo -e "${GREEN} Alpine Linux:${RESET} Use 'alpine:latest' (supports multi-arch)"
#     echo -e "${GREEN} Ubuntu:${RESET} Use 'ubuntu:20.04' or newer (supports multi-arch)"
#     echo -e "${GREEN} Python:${RESET} Use 'python:3-alpine' or 'python:3-slim' (supports multi-arch)"
#     echo -e "${GREEN} Node.js:${RESET} Use 'node:lts-alpine' or 'node:lts-slim' (supports multi-arch)"
#     echo -e "${GREEN} Nginx:${RESET} Use 'nginx:alpine' or 'nginx:stable' (supports multi-arch)"
#     echo -e "${GREEN} Redis:${RESET} Use 'redis:alpine' (supports multi-arch)"
#     echo -e "${GREEN} PostgreSQL:${RESET} Use 'postgres:alpine' (supports multi-arch)"
#     echo -e "${YELLOW} For more information on multi-arch images, visit:${RESET}"
#     echo -e "  https://docs.docker.com/build/building/multi-platform/"
# }

# Function to get Amazon Q recommendations for ARM64 optimization
# get_q_recommendations() {
#     if [[ "$USE_AMAZON_Q" == false ]]; then
#         return
#     fi

#     echo -e "\n${BLUE}╔════════════════════════════════════════════════════════════╗${RESET}"
#     echo -e "${BLUE}║             AMAZON Q RECOMMENDATIONS                       ║${RESET}"
#     echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${RESET}"

#     echo -e "${CYAN}Asking Amazon Q for best practices for ARM64 Docker images...${RESET}"
#     q chat "What are the best practices for optimizing Docker images for ARM64 architecture? Provide concise, practical tips."
# }

# Main Execution
install_dependencies

echo -e "${CYAN}Cloning repository: $REPO_URL...${RESET}"

# Clone or pull latest changes from GitHub repo
if [[ -d "$REPO_NAME" ]]; then
    echo -e "${CYAN}Repository already exists. Pulling latest changes...${RESET}"
    cd "$REPO_NAME" || exit 1
    git pull || { echo -e "${RED} Failed to pull latest changes. Exiting...${RESET}"; exit 1; }
else
    git clone "$REPO_URL" || { echo -e "${RED} Failed to clone repository. Exiting...${RESET}"; exit 1; }
    cd "$REPO_NAME" || exit 1
fi

echo -e "${CYAN}Scanning for Dockerfiles...${RESET}"

# Find all Dockerfiles in subdirectories
DOCKERFILES=$(find . -type f -iname "Dockerfile")

if [[ -z "$DOCKERFILES" ]]; then
    echo -e "${RED} No Dockerfiles found in repository!${RESET}"
    exit 0
fi

# Loop through each Dockerfile and process it
for DOCKERFILE in $DOCKERFILES; do
    process_dockerfile "$DOCKERFILE"
    echo "----------------------------------------"
done

# Provide suggestions for ARM64 compatibility
#suggest_arm64_alternatives

# Get Amazon Q recommendations if available
# if [[ "$USE_AMAZON_Q" == true ]]; then
#     get_q_recommendations
# fi

echo " "
echo -e "${CYAN}Analysis complete!${RESET}"