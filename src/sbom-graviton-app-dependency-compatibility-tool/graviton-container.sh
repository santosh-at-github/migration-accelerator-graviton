#!/bin/bash

# Define color codes
GREEN="\033[1;32m"
RED="\033[1;31m"
CYAN="\033[1;36m"
YELLOW="\033[1;33m"
BLUE="\033[1;34m"
RESET="\033[0m"

# Check for repos file argument and get absolute path
REPOS_FILE="${1}"

if [[ -z "$REPOS_FILE" ]]; then
    echo -e "${RED}No repository list file provided${RESET}"
    echo "Usage: $0 <repos-file>"
    echo "Provide a text file with one repository URL per line."
    echo "Example: $0 my-repos.txt"
    exit 1
fi

if [[ ! -f "$REPOS_FILE" ]]; then
    echo -e "${RED}Repository list file not found: $REPOS_FILE${RESET}"
    echo "Usage: $0 <repos-file>"
    echo "Create a text file with one repository URL per line."
    echo "Example file content:"
    echo "  https://github.com/user/repo1.git"
    echo "  https://github.com/user/repo2.git"
    exit 1
fi

# Get absolute path before changing directories
REPOS_FILE=$(realpath "$REPOS_FILE")
echo -e "${CYAN}Reading repository URLs from: $REPOS_FILE${RESET}"

# Initialize CSV output file
CSV_OUTPUT="$HOME/docker_arm64_recommendations_$(date +%Y%m%d_%H%M%S).csv"
echo "Repository,Base Image,ARM64 Supported,Recommended Alternative,Build Verified" > "$CSV_OUTPUT"
echo -e "${CYAN}CSV report will be saved to: $CSV_OUTPUT${RESET}"

cd /tmp/

# Function to install dependencies
install_dependencies() {
    echo -e "${CYAN}Checking required dependencies...${RESET}"

    # Install Git if not present
    if ! command -v git &>/dev/null; then
        echo -e "${RED}Git not found. Installing...${RESET}"
        sudo apt-get update && sudo apt-get install -y git || { echo -e "${RED}Failed to install Git. Exiting...${RESET}"; exit 1; }
    else
        echo -e "${GREEN}✓ Git is already installed${RESET}"
    fi

    # Install Docker
    if ! command -v docker &>/dev/null; then
        echo -e "${RED}Docker not found. Installing...${RESET}"
        sudo apt-get update && sudo apt-get install -y docker.io || { echo -e "${RED}Failed to install Docker. Exiting...${RESET}"; exit 1; }
    else
        echo -e "${GREEN}✓ Docker is already installed${RESET}"
    fi

    # Install Skopeo
    if ! command -v skopeo &>/dev/null; then
        echo -e "${RED}Skopeo not found. Installing...${RESET}"
        sudo apt-get update && sudo apt-get install -y skopeo || { echo -e "${RED}Failed to install Skopeo. Exiting...${RESET}"; exit 1; }
    else
        echo -e "${GREEN}✓ Skopeo is already installed${RESET}"
    fi

    # Install jq if not present
    if ! command -v jq &>/dev/null; then
        echo -e "${RED}jq not found. Installing...${RESET}"
        sudo apt-get update && sudo apt-get install -y jq || { echo -e "${RED}Failed to install jq. Exiting...${RESET}"; exit 1; }
    else
        echo -e "${GREEN}✓ jq is already installed${RESET}"
    fi
}
# Function to test ARM64 build with base image
test_arm64_build() {
    local base_image=$1
    local test_dockerfile="Dockerfile.test"
    
    # Create simple test Dockerfile
    cat > "$test_dockerfile" << EOF
FROM $base_image
RUN echo "ARM64 build test successful"
EOF
    
    # Try ARM64 build
    if docker build --platform linux/arm64 -t "test-arm64:$(date +%s)" -f "$test_dockerfile" . >/dev/null 2>&1; then
        rm -f "$test_dockerfile"
        return 0
    else
        rm -f "$test_dockerfile"
        return 1
    fi
}

# Function to check if image supports ARM64
check_arm64_support() {
    local image=$1
    local raw_json=$(skopeo inspect --raw docker://"$image" 2>/dev/null)
    
    if [[ -z "$raw_json" ]]; then
        return 1
    fi
    
    if echo "$raw_json" | jq -r '.manifests[]? | select(.platform.architecture == "arm64") | .platform.architecture' 2>/dev/null | grep -q "arm64"; then
        return 0
    elif echo "$raw_json" | jq -r '.architecture' 2>/dev/null | grep -q "arm64"; then
        return 0
    else
        return 1
    fi
}

# Function to write base image results to CSV
write_base_image_csv() {
    local repo_name=$1
    local base_image=$2
    local arm64_supported=$3
    local recommendation=""
    local build_verified="N/A"
    
    if [[ "$arm64_supported" == "No" ]]; then
        local suggested_image=""
        case "$base_image" in
            *alpine*)
                suggested_image="alpine:latest"
                ;;
            *ubuntu*)
                suggested_image="ubuntu:22.04"
                ;;
            *debian*)
                suggested_image="debian:bullseye"
                ;;
            *python*)
                suggested_image="python:3.11-slim"
                ;;
            *node*)
                suggested_image="node:18-alpine"
                ;;
            *nginx*)
                suggested_image="nginx:alpine"
                ;;
            *redis*)
                suggested_image="redis:alpine"
                ;;
            *)
                recommendation="Check official registry for ARM64 support"
                ;;
        esac
        
        if [[ -n "$suggested_image" ]]; then
            echo "  → Validating recommended image: $suggested_image" >&2
            if check_arm64_support "$suggested_image"; then
                recommendation="$suggested_image (ARM64 verified)"
            else
                recommendation="$suggested_image (ARM64 not verified)"
            fi
        fi
    else
        recommendation="N/A"
        echo "  → Testing ARM64 build with: $base_image" >&2
        if test_arm64_build "$base_image"; then
            build_verified="Yes"
        else
            build_verified="Failed"
        fi
    fi
    
    echo "$repo_name,$base_image,$arm64_supported,$recommendation,$build_verified" >> "$CSV_OUTPUT"
}

# Global variables to track validation issues and results
VALIDATION_ISSUES=0
DOCKERFILE_RESULTS=""
BASE_IMAGES_LIST=""
BASE_IMAGES_STATUS=""

# Function to analyze Python dependencies for ARM64 compatibility
analyze_python_dependencies() {
    local dir=$1
    local requirements_file="$dir/requirements.txt"
    local found_issues=false

    if [[ -f "$requirements_file" ]]; then
        echo -e "${CYAN}Found requirements.txt. Analyzing Python dependencies for ARM64 compatibility...${RESET}"

        # Known problematic packages for ARM64
        local problematic_packages=(
            "tensorflow==1.*" "tensorflow<2.4"
            "torch<1.8" "torchvision<0.9"
            "opencv-python<4.5" "opencv-contrib-python<4.5"
            "numpy<1.19" "scipy<1.5" "pandas<1.0"
            "scikit-learn<0.24" "matplotlib<3.3"
            "pillow<8.0" "cryptography<3.0"
            "psycopg2<2.8" "mysqlclient<2.0"
            "lxml<4.6" "pyzmq<20.0"
        )

        # Check for version-specific issues
        while IFS= read -r line; do
            # Skip comments and empty lines
            [[ "$line" =~ ^[[:space:]]*# ]] && continue
            [[ -z "${line// }" ]] && continue

            package_line=$(echo "$line" | tr '[:upper:]' '[:lower:]')
            
            for problematic in "${problematic_packages[@]}"; do
                if [[ "$package_line" == *"${problematic%<*}"* ]]; then
                    echo -e "${RED}  ⚠ Potential ARM64 issue: $line${RESET}"
                    echo -e "    Recommendation: Update to newer version that supports ARM64"
                    found_issues=true
                    ((VALIDATION_ISSUES++))
                fi
            done

            # Check for packages that commonly have ARM64 issues
            case "$package_line" in
                *"tensorflow"*|*"torch"*|*"opencv"*)
                    echo -e "${YELLOW}  ℹ ARM64 note: $line${RESET}"
                    echo -e "    Verify this version has ARM64 wheels available"
                    ;;
                *"psycopg2"*)
                    echo -e "${YELLOW}  ℹ Consider using psycopg2-binary for ARM64${RESET}"
                    ;;
                *"mysqlclient"*)
                    echo -e "${YELLOW}  ℹ May require additional build dependencies on ARM64${RESET}"
                    ;;
                *"grpcio"*|*"grpc"*)
                    echo -e "${YELLOW}  ℹ gRPC may need compilation on ARM64 - check for wheels${RESET}"
                    ;;
            esac
        done < "$requirements_file"

        # Check for setup.py and pyproject.toml for additional dependencies
        if [[ -f "$dir/setup.py" ]]; then
            echo -e "${CYAN}  Found setup.py - checking for native extensions...${RESET}"
            if grep -q "ext_modules\|Extension\|Cython" "$dir/setup.py"; then
                echo -e "${YELLOW}  ⚠ Native extensions detected - ensure ARM64 compatibility${RESET}"
            fi
        fi

        if [[ -f "$dir/pyproject.toml" ]]; then
            echo -e "${CYAN}  Found pyproject.toml - checking build requirements...${RESET}"
            if grep -q "build-backend\|setuptools_scm\|cython" "$dir/pyproject.toml"; then
                echo -e "${YELLOW}  ℹ Build system detected - verify ARM64 build tools${RESET}"
            fi
        fi

        if [[ "$found_issues" == false ]]; then
            echo -e "${GREEN}  ✓ No obvious ARM64 compatibility issues found${RESET}"
        fi
        return 0
    fi
    return 1
}

# Function to analyze Node.js dependencies
analyze_nodejs_dependencies() {
    local dir=$1
    local package_file="$dir/package.json"
    local found_issues=false

    if [[ -f "$package_file" ]]; then
        echo -e "${CYAN}Found package.json. Analyzing Node.js dependencies for ARM64 compatibility...${RESET}"

        # Known problematic Node.js packages
        local problematic_packages=(
            "node-sass" "fibers" "sharp" "canvas"
            "sqlite3" "bcrypt" "argon2" "scrypt"
            "grpc" "@grpc/grpc-js" "protobufjs"
        )

        for package in "${problematic_packages[@]}"; do
            if grep -q "\"$package\"" "$package_file"; then
                echo -e "${YELLOW}  ⚠ ARM64 note: $package${RESET}"
                echo -e "    This package may need native compilation - ensure ARM64 support"
                found_issues=true
                ((VALIDATION_ISSUES++))
            fi
        done

        if [[ "$found_issues" == false ]]; then
            echo -e "${GREEN}  ✓ No obvious ARM64 compatibility issues found${RESET}"
        fi
        return 0
    fi
    return 1
}

# Function to analyze Go dependencies
analyze_go_dependencies() {
    local dir=$1
    local go_mod_file="$dir/go.mod"
    local found_issues=false

    if [[ -f "$go_mod_file" ]]; then
        echo -e "${CYAN}Found go.mod. Analyzing Go dependencies for ARM64 compatibility...${RESET}"

        # Check for CGO usage which might have ARM64 issues
        if find "$dir" -name "*.go" -exec grep -l "import \"C\"" {} \; 2>/dev/null | head -1 >/dev/null; then
            echo -e "${YELLOW}  ⚠ CGO usage detected - ensure C libraries support ARM64${RESET}"
            found_issues=true
            ((VALIDATION_ISSUES++))
        fi

        # Check for known problematic Go packages
        local problematic_go_packages=(
            "github.com/mattn/go-sqlite3"
            "github.com/go-sql-driver/mysql"
            "github.com/lib/pq"
        )

        for package in "${problematic_go_packages[@]}"; do
            if grep -q "$package" "$go_mod_file"; then
                echo -e "${YELLOW}  ℹ Database driver detected: $package${RESET}"
                echo -e "    Verify ARM64 compatibility for native components"
            fi
        done

        if [[ "$found_issues" == false ]]; then
            echo -e "${GREEN}  ✓ No obvious ARM64 compatibility issues found${RESET}"
        fi
        return 0
    fi
    return 1
}

# Function to analyze Java/Maven dependencies
analyze_java_dependencies() {
    local dir=$1
    local found_issues=false

    if [[ -f "$dir/pom.xml" ]]; then
        echo -e "${CYAN}Found pom.xml. Analyzing Maven dependencies for ARM64 compatibility...${RESET}"

        # Check for native libraries
        if grep -q "jna\|jni\|native" "$dir/pom.xml"; then
            echo -e "${YELLOW}  ⚠ Native library dependencies detected${RESET}"
            echo -e "    Ensure native libraries have ARM64 versions"
            found_issues=true
            ((VALIDATION_ISSUES++))
        fi

        return 0
    elif [[ -f "$dir/build.gradle" || -f "$dir/build.gradle.kts" ]]; then
        echo -e "${CYAN}Found Gradle build file. Analyzing dependencies for ARM64 compatibility...${RESET}"

        local gradle_file="$dir/build.gradle"
        [[ -f "$dir/build.gradle.kts" ]] && gradle_file="$dir/build.gradle.kts"

        if grep -q "jna\|jni\|native" "$gradle_file"; then
            echo -e "${YELLOW}  ⚠ Native library dependencies detected${RESET}"
            echo -e "    Ensure native libraries have ARM64 versions"
            found_issues=true
            ((VALIDATION_ISSUES++))
        fi

        return 0
    fi
    return 1
}

# Function to analyze Rust dependencies
analyze_rust_dependencies() {
    local dir=$1
    local cargo_file="$dir/Cargo.toml"

    if [[ -f "$cargo_file" ]]; then
        echo -e "${CYAN}Found Cargo.toml. Analyzing Rust dependencies for ARM64 compatibility...${RESET}"

        # Rust generally has good ARM64 support, but check for system dependencies
        if grep -q "openssl\|libssl\|pkg-config" "$cargo_file"; then
            echo -e "${YELLOW}  ℹ System library dependencies detected${RESET}"
            echo -e "    Ensure system libraries are available for ARM64"
        fi

        echo -e "${GREEN}  ✓ Rust generally has excellent ARM64 support${RESET}"
        return 0
    fi
    return 1
}

# Function to analyze multi-stage build and platform support
analyze_multistage_build() {
    local dockerfile=$1
    
    echo -e "${CYAN}Analyzing multi-stage build configuration...${RESET}"
    
    # Check for BuildKit platform variables
    if grep -q "BUILDPLATFORM\|TARGETPLATFORM\|TARGETARCH\|TARGETOS" "$dockerfile"; then
        echo -e "${GREEN}  ✓ Found BuildKit platform variables - excellent for multi-arch builds${RESET}"
        
        # List the platform variables found
        local platform_vars=$(grep -o "BUILDPLATFORM\|TARGETPLATFORM\|TARGETARCH\|TARGETOS" "$dockerfile" | sort -u)
        echo -e "${CYAN}    Platform variables detected: ${platform_vars//$'\n'/, }${RESET}"
    fi
    
    # Check for --platform flags in FROM statements
    if grep -q "FROM --platform=" "$dockerfile"; then
        echo -e "${GREEN}  ✓ Found --platform flags in FROM statements${RESET}"
        grep -n "FROM --platform=" "$dockerfile" | while read -r line; do
            echo -e "${CYAN}    $line${RESET}"
        done
    fi
    
    # Check for multi-stage build
    local stage_count=$(grep -c "^FROM.*AS" "$dockerfile")
    if [[ $stage_count -gt 0 ]]; then
        echo -e "${GREEN}  ✓ Multi-stage build detected ($stage_count stages)${RESET}"
        
        # List all build stages
        echo -e "${CYAN}    Build stages:${RESET}"
        grep -n "^FROM.*AS" "$dockerfile" | while read -r line; do
            local stage_name=$(echo "$line" | sed -E 's/.*AS[[:space:]]+([^[:space:]]+).*/\1/')
            echo -e "${CYAN}      - $stage_name${RESET}"
        done
    fi
    
    # Check for CGO_ENABLED=0 (good for cross-compilation)
    if grep -q "CGO_ENABLED=0" "$dockerfile"; then
        echo -e "${GREEN}  ✓ CGO disabled - excellent for cross-platform Go builds${RESET}"
    fi
}

# Function to extract and analyze all FROM statements
analyze_base_images() {
    local dockerfile=$1
    local all_compatible=true
    
    echo -e "${CYAN}Analyzing all base images in multi-stage build...${RESET}"
    
    # Initialize global variables for CSV output
    BASE_IMAGES_LIST=""
    BASE_IMAGES_STATUS=""
    
    # Extract all FROM statements, including those with platform flags and variables
    local from_statements=$(grep -E '^FROM' "$dockerfile")
    
    while IFS= read -r from_line; do
        # Skip empty lines
        [[ -z "$from_line" ]] && continue
        
        # Extract image name, handling various FROM formats
        local base_image=""
        
        if [[ "$from_line" =~ FROM[[:space:]]+--platform=[^[:space:]]+[[:space:]]+([^[:space:]]+) ]]; then
            # FROM --platform=... image
            base_image="${BASH_REMATCH[1]}"
        elif [[ "$from_line" =~ FROM[[:space:]]+([^[:space:]]+)[[:space:]]+AS ]]; then
            # FROM image AS stage
            base_image="${BASH_REMATCH[1]}"
        elif [[ "$from_line" =~ FROM[[:space:]]+([^[:space:]]+) ]]; then
            # FROM image
            base_image="${BASH_REMATCH[1]}"
        fi
        
        # Skip if it's a stage reference (no registry/image format)
        if [[ "$base_image" =~ ^[a-zA-Z0-9_-]+$ ]] && ! [[ "$base_image" =~ : ]]; then
            echo -e "${YELLOW}  → Skipping build stage reference: $base_image${RESET}"
            continue
        fi
        
        # Skip if it contains variables that we can't resolve
        if [[ "$base_image" =~ \$ ]]; then
            echo -e "${CYAN}  → Base image with variables: $base_image${RESET}"
            echo -e "${YELLOW}    Cannot validate at build time - ensure ARM64 compatibility${RESET}"
            write_base_image_csv "$REPO_NAME" "$base_image" "Unknown"
            continue
        fi
        
        echo -e "${CYAN}  → Checking base image: $base_image${RESET}"
        
        # Check ARM64 support for this base image
        local raw_json=$(skopeo inspect --raw docker://"$base_image" 2>/dev/null)
        
        if [[ -z "$raw_json" ]]; then
            echo -e "${RED}    ✗ Unable to fetch details for $base_image${RESET}"
            all_compatible=false
            ((VALIDATION_ISSUES++))
            write_base_image_csv "$REPO_NAME" "$base_image" "Error"
            continue
        fi
        
        # Check for ARM64 support
        local arm64_found=false
        
        if echo "$raw_json" | jq -e '.manifests' >/dev/null 2>&1; then
            if echo "$raw_json" | jq -r '.manifests[]? | select(.platform.architecture == "arm64") | .platform.architecture' 2>/dev/null | grep -q "arm64"; then
                arm64_found=true
            fi
        elif echo "$raw_json" | jq -e '.architecture' >/dev/null 2>&1; then
            local arch=$(echo "$raw_json" | jq -r '.architecture' 2>/dev/null)
            if [[ "$arch" == "arm64" ]]; then
                arm64_found=true
            fi
        fi
        
        if [[ "$arm64_found" == true ]]; then
            echo -e "${GREEN}    ✓ Supports ARM64${RESET}"
            write_base_image_csv "$REPO_NAME" "$base_image" "Yes"
        else
            echo -e "${RED}    ✗ Does NOT support ARM64${RESET}"
            all_compatible=false
            ((VALIDATION_ISSUES++))
            write_base_image_csv "$REPO_NAME" "$base_image" "No"
        fi
        
    done <<< "$from_statements"
    
    return $([ "$all_compatible" = true ] && echo 0 || echo 1)
}

# Function to analyze system dependencies in Dockerfile
analyze_dockerfile_dependencies() {
    local dockerfile=$1
    local found_issues=false

    echo -e "${CYAN}Analyzing Dockerfile for ARM64 compatibility...${RESET}"

    # Check for architecture-specific installations
    if grep -q "x86_64\|amd64\|i386" "$dockerfile"; then
        echo -e "${RED}  ⚠ Found architecture-specific references in Dockerfile${RESET}"
        grep -n "x86_64\|amd64\|i386" "$dockerfile" | while read -r line; do
            echo -e "    Line: $line"
        done
        found_issues=true
        ((VALIDATION_ISSUES++))
    fi

    # Check for problematic system packages
    local problematic_apt_packages=(
        "libc6-dev-i386" "gcc-multilib" "lib32z1-dev"
        "oracle-java" "sun-java" "openjdk-.*-jre-headless.*amd64"
    )

    for package in "${problematic_apt_packages[@]}"; do
        if grep -q "$package" "$dockerfile"; then
            echo -e "${RED}  ⚠ Potentially problematic package: $package${RESET}"
            found_issues=true
            ((VALIDATION_ISSUES++))
        fi
    done

    # Check for manual binary downloads
    if grep -q "wget.*x86_64\|curl.*x86_64\|wget.*amd64\|curl.*amd64" "$dockerfile"; then
        echo -e "${RED}  ⚠ Found x86_64/amd64 binary downloads${RESET}"
        grep -n "wget.*x86_64\|curl.*x86_64\|wget.*amd64\|curl.*amd64" "$dockerfile" | while read -r line; do
            echo -e "    Line: $line"
        done
        found_issues=true
        ((VALIDATION_ISSUES++))
    fi

    if [[ "$found_issues" == false ]]; then
        echo -e "${GREEN}  ✓ No obvious ARM64 compatibility issues in Dockerfile${RESET}"
    fi

    return 0
}

# Function to check image architecture and build for ARM64
process_dockerfile() {
    local dockerfile=$1
    local dir=$(dirname "$dockerfile")
    
    echo -e "${CYAN}Checking Dockerfile: $dockerfile${RESET}"

    # Reset validation issues counter for this dockerfile
    VALIDATION_ISSUES=0
    
    # Analyze dependencies first
    echo -e "\n${CYAN}=== COMPREHENSIVE ARM64 ANALYSIS ===${RESET}"
    
    # Analyze multi-stage build and platform configuration
    analyze_multistage_build "$dockerfile"
    echo ""
    
    # Analyze all base images
    analyze_base_images "$dockerfile"
    echo ""
    
    # Analyze Dockerfile for system dependencies
    analyze_dockerfile_dependencies "$dockerfile"
    
    # Analyze language-specific dependencies
    analyze_python_dependencies "$dir"
    analyze_nodejs_dependencies "$dir"
    analyze_go_dependencies "$dir"
    analyze_java_dependencies "$dir"
    analyze_rust_dependencies "$dir"
    
    echo -e "${CYAN}=== END ANALYSIS ===${RESET}\n"

    # Validation summary - automatic proceed
    if [[ $VALIDATION_ISSUES -gt 0 ]]; then
        echo -e "${RED}⚠ VALIDATION SUMMARY: Found $VALIDATION_ISSUES potential ARM64 compatibility issues${RESET}"
        echo -e "${YELLOW}These issues may cause build failures or runtime problems on ARM64${RESET}"
        echo -e "${CYAN}Proceeding with build anyway - monitoring for failures...${RESET}"
        echo ""
    else
        echo -e "${GREEN}✅ VALIDATION PASSED: No ARM64 compatibility issues detected${RESET}"
        echo -e "${CYAN}Proceeding with ARM64 build...${RESET}"
        echo ""
    fi

    # Always proceed with build - validation is informational only
    echo -e "${CYAN}Attempting ARM64 build for $REPO_NAME...${RESET}"
    BUILD_TAG="$REPO_NAME:arm64-$(date +%s)"

    if docker build --platform linux/arm64 -t "$BUILD_TAG" -f "$dockerfile" .; then
        echo -e "${GREEN}✅ Build successful for ARM64${RESET}"
        echo -e "${GREEN}Image tagged as: $BUILD_TAG${RESET}"
        
        # Show validation correlation with build success
        if [[ $VALIDATION_ISSUES -gt 0 ]]; then
            echo -e "${YELLOW}Note: Build succeeded despite $VALIDATION_ISSUES validation warnings${RESET}"
        fi
    else
        echo -e "${RED}❌ Build failed for ARM64${RESET}"
        
        # Show validation correlation with build failure
        if [[ $VALIDATION_ISSUES -gt 0 ]]; then
            echo -e "${RED}Build failure likely related to the $VALIDATION_ISSUES validation issues found${RESET}"
            echo -e "${CYAN}Review the validation warnings above for potential fixes${RESET}"
        else
            echo -e "${YELLOW}Build failed despite passing validation - may be runtime or build-specific issues${RESET}"
        fi
        return 1
    fi
}

# Function to process a single repository
process_repository() {
    local repo_url=$1
    local repo_name=$(basename -s .git "$repo_url")
    
    # Set global variable for CSV output
    REPO_NAME="$repo_name"
    
    echo -e "\n${CYAN}╔════════════════════════════════════════════════════════════╗${RESET}"
    echo -e "${CYAN}║ Processing Repository: $(printf "%-42s" "$repo_name") ║${RESET}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${RESET}"
    
    echo -e "${CYAN}Repository URL: $repo_url${RESET}"
    
    # Initialize CSV data for this repository
    local csv_repo_name="$repo_name"
    local csv_repo_url="$repo_url"
    local csv_dockerfiles_found=0
    local csv_base_images=""
    local csv_base_images_status=""
    local csv_arm64_compatible="Unknown"
    local csv_build_status="Not Attempted"
    local csv_validation_issues=0
    local csv_notes=""
    local csv_recommendation=""
    
    # Clone or update repository
    if [[ -d "$repo_name" ]]; then
        echo -e "${CYAN}Repository already exists. Removing and re-cloning to avoid permission issues...${RESET}"
        sudo rm -rf "$repo_name"
    fi
    
    if git clone "$repo_url" 2>/dev/null; then
        echo -e "${GREEN}✓ Successfully cloned repository${RESET}"
    else
        echo -e "${RED}✗ Failed to clone repository: $repo_url${RESET}"
        echo -e "${YELLOW}Skipping to next repository...${RESET}"
        return 1
    fi
    
    cd "$repo_name" || { echo -e "${RED}Failed to enter repository directory${RESET}"; return 1; }
    
    # Find all Dockerfiles
    local dockerfiles=$(find . -type f -iname "Dockerfile" -o -name "*.dockerfile" -o -name "Dockerfile.*")
    
    if [[ -z "$dockerfiles" ]]; then
        echo -e "${YELLOW}No Dockerfiles found in repository: $repo_name${RESET}"
        cd ..
        return 0
    fi
    
    echo -e "${CYAN}Found Dockerfiles:${RESET}"
    echo "$dockerfiles" | while read -r dockerfile; do
        echo -e "  → $dockerfile"
    done
    echo ""
    
    # Process each Dockerfile
    local dockerfile_count=0
    local successful_builds=0
    local failed_builds=0
    local total_validation_issues=0
    local all_base_images=""
    local all_base_images_status=""
    
    while IFS= read -r dockerfile; do
        [[ -z "$dockerfile" ]] && continue
        ((dockerfile_count++))
        
        echo -e "${CYAN}Processing Dockerfile $dockerfile_count: $dockerfile${RESET}"
        
        # Reset global validation counter for this dockerfile
        VALIDATION_ISSUES=0
        BASE_IMAGES_LIST=""
        BASE_IMAGES_STATUS=""
        
        if process_dockerfile "$dockerfile"; then
            ((successful_builds++))
            echo -e "${GREEN}✓ Dockerfile processed successfully${RESET}"
        else
            ((failed_builds++))
            echo -e "${RED}✗ Dockerfile processing failed${RESET}"
        fi
        
        # Accumulate validation issues and base image info
        ((total_validation_issues += VALIDATION_ISSUES))
        
        # Collect base images from all Dockerfiles
        if [[ -n "$BASE_IMAGES_LIST" ]]; then
            if [[ -n "$all_base_images" ]]; then
                all_base_images="$all_base_images | $BASE_IMAGES_LIST"
                all_base_images_status="$all_base_images_status | $BASE_IMAGES_STATUS"
            else
                all_base_images="$BASE_IMAGES_LIST"
                all_base_images_status="$BASE_IMAGES_STATUS"
            fi
        fi
        
        echo -e "${CYAN}$(printf '%.0s─' {1..60})${RESET}"
    done <<< "$dockerfiles"
    
    # Repository summary
    echo -e "\n${CYAN}Repository Summary for $repo_name:${RESET}"
    echo -e "  Dockerfiles found: $dockerfile_count"
    echo -e "  Successful builds: ${GREEN}$successful_builds${RESET}"
    echo -e "  Failed builds: ${RED}$failed_builds${RESET}"
    echo -e "  Validation issues: ${YELLOW}$total_validation_issues${RESET}"
    
    cd ..
    return 0
}

# Main Execution
install_dependencies

# Initialize counters
TOTAL_REPOS=0
SUCCESSFUL_REPOS=0
FAILED_REPOS=0

echo -e "${CYAN}Reading repositories from $REPOS_FILE...${RESET}"

# Process each repository - simple line by line reading
while IFS= read -r repo_url || [[ -n "$repo_url" ]]; do
    # Skip empty lines
    [[ -z "$repo_url" ]] && continue
    
    ((TOTAL_REPOS++))
    
    echo -e "\n${BLUE}Processing repository $TOTAL_REPOS: $repo_url${RESET}"
    
    if process_repository "$repo_url"; then
        ((SUCCESSFUL_REPOS++))
    else
        ((FAILED_REPOS++))
    fi
    
done < "$REPOS_FILE"

# Final summary
echo -e "\n${CYAN}╔════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}║                    FINAL SUMMARY                           ║${RESET}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${RESET}"
echo -e "Total repositories processed: $TOTAL_REPOS"
echo -e "Successful: ${GREEN}$SUCCESSFUL_REPOS${RESET}"
echo -e "Failed: ${RED}$FAILED_REPOS${RESET}"
echo -e "Success rate: $(( TOTAL_REPOS > 0 ? (SUCCESSFUL_REPOS * 100) / TOTAL_REPOS : 0 ))%"
echo -e "\n${GREEN}✅ CSV Report Generated: $CSV_OUTPUT${RESET}"
echo -e "${CYAN}The CSV file contains detailed ARM64 compatibility analysis for each repository${RESET}"
echo -e "\n${CYAN}Analysis complete!${RESET}"
