#!/bin/bash

# Define color codes
GREEN="\033[1;32m"
RED="\033[1;31m"
CYAN="\033[1;36m"
RESET="\033[0m"

# GitHub repository to clone (pass as an argument)
read -p "Enter the repo URL of your App that containers Dockerfile: " REPO_URL
cd /tmp/

if [[ -z "$REPO_URL" ]]; then
    echo -e "${RED} No GitHub repository URL provided!${RESET}"
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
        echo -e "${GREEN}✓ Git is already installed${RESET}"
    fi

    # Install Docker
    if ! command -v docker &>/dev/null; then
        echo -e "${RED}Docker not found. Installing...${RESET}"
        sudo apt-get update && sudo apt-get install -y docker.io || { echo -e "${RED} Failed to install Docker. Exiting...${RESET}"; exit 1; }
    else
        echo -e "${GREEN}✓ Docker is already installed${RESET}"
    fi

    # Install Skopeo
    if ! command -v skopeo &>/dev/null; then
        echo -e "${RED}Skopeo not found. Installing...${RESET}"
        sudo apt-get update && sudo apt-get install -y skopeo || { echo -e "${RED} Failed to install Skopeo. Exiting...${RESET}"; exit 1; }
    else
        echo -e "${GREEN}✓ Skopeo is already installed${RESET}"
    fi
}
# Function to check image architecture and build for ARM64
process_dockerfile() {
    local dockerfile=$1
    echo -e "${CYAN}Checking Dockerfile: $dockerfile${RESET}"

    # Extract base images (ignoring '--platform=' flags)
    BASE_IMAGE=$(grep -E '^FROM\s+' "$dockerfile" | sed -E 's/.*FROM\s+([^ ]+).*/\1/' | head -1)

    if [[ -z "$BASE_IMAGE" ]]; then
        echo -e "${RED} No valid base image found in '$dockerfile'. Skipping...${RESET}"
        return 1
    fi

    echo -e "→ Checking base image: ${CYAN}$BASE_IMAGE${RESET}"

    # Check if image supports ARM64 using skopeo
    echo "→ Inspecting image for ARM64 support..."
    RAW_JSON=$(skopeo inspect --raw docker://"$BASE_IMAGE" 2>/dev/null)

    if [[ -z "$RAW_JSON" ]]; then
        echo -e "${RED} Unable to fetch details for $BASE_IMAGE. Skipping...${RESET}"
        return 1
    fi

    if echo "$RAW_JSON" | jq -r '.manifests[].platform.architecture' | grep -q "arm64"; then
        echo -e "${GREEN} $BASE_IMAGE supports ARM64${RESET}"

        # Attempt ARM64 build
        sleep 2
        echo ''
        echo "Attempting to build $REPO_NAME on ARM64 ..."
        sleep 2
        echo ''
        BUILD_TAG="$REPO_NAME:arm64-$(date +%s)"

        if docker build --platform linux/arm64 -t "$BUILD_TAG" -f "$dockerfile" . 1>/dev/null; then
            sleep 2
            echo ''
            echo -e "${GREEN} Build successful for ARM64${RESET}"
        else
            sleep 2
            echo ''
            echo -e "${RED} Build failed for ARM64${RESET}"
            return 1
        fi
    else
        sleep 2
        echo ''
        echo -e "${RED} $BASE_IMAGE does NOT support ARM64. Skipping build.${RESET}"
        return 1
    fi
}

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

echo " "
sleep 0.2
echo -e "${CYAN}Image build complete!${RESET}"