#!/bin/bash

# SBOM Graviton App Dependency Compatibility Tool - Build Setup Script
# This script handles the heavy lifting for SBOM analysis and report generation

# Note: We don't use 'set -e' here because we want to handle upload failures gracefully
# and continue processing other files even if some uploads fail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to upload file with error handling
upload_file() {
    local file_path="$1"
    local s3_path="$2"
    
    if [ -f "$file_path" ]; then
        log_info "Uploading $file_path to $s3_path"
        if aws s3 cp "$file_path" "$s3_path"; then
            log_success "Successfully uploaded $file_path"
            return 0
        else
            log_error "Failed to upload $file_path"
            return 1
        fi
    else
        log_warning "File not found: $file_path"
        return 1
    fi
}

# Function to process Maven results
process_maven_results() {
    local customer_key="$1"
    local bucket_name="$2"
    
    log_info "Processing Maven results..."
    
    local upload_count=0
    
    # Upload Maven-specific files
    if upload_file "./assets/java/errors.txt" "s3://$bucket_name/reports/$customer_key/maven/errors.txt"; then
        ((upload_count++))
    fi
    
    if upload_file "./arm_compatibility_results/arm_compatibility_results.xlsx" "s3://$bucket_name/reports/$customer_key/maven/arm-compatibility.xlsx"; then
        ((upload_count++))
    fi
    
    if upload_file "./arm_compatibility_results/arm_compatibility_report.md" "s3://$bucket_name/reports/$customer_key/maven/arm-compatibility-report.md"; then
        ((upload_count++))
    fi
    
    log_info "Maven: Uploaded $upload_count files"
}

# Function to process Python/pip results
process_pip_results() {
    local customer_key="$1"
    local bucket_name="$2"
    
    log_info "Processing Python/pip results..."
    
    local upload_count=0
    local timestamp=$(date +%Y-%m-%d-%H-%M-%S)
    
    # Upload Python-specific files
    if upload_file "graviton_compatability_pip.xlsx" "s3://$bucket_name/reports/$customer_key/pip/dependencies-$timestamp.xlsx"; then
        ((upload_count++))
    fi
    
    if upload_file "discovery_dependencies_small.xlsx" "s3://$bucket_name/reports/$customer_key/pip/discovery_dependencies_small.xlsx"; then
        ((upload_count++))
    fi
    
    log_info "Python/pip: Uploaded $upload_count files"
}

# Function to process NPM results
process_npm_results() {
    local customer_key="$1"
    local bucket_name="$2"
    
    log_info "Processing NPM results..."
    
    local upload_count=0
    
    # Upload NPM-specific files
    if upload_file "graviton_compatibility_npm.xlsx" "s3://$bucket_name/reports/$customer_key/npm/graviton_compatibility_npm.xlsx"; then
        ((upload_count++))
    fi
    
    if upload_file "npm_compatibility_results.xlsx" "s3://$bucket_name/reports/$customer_key/npm/npm_compatibility_results.xlsx"; then
        ((upload_count++))
    fi
    
    if upload_file "temp_npm_install.log" "s3://$bucket_name/reports/$customer_key/npm/temp_npm_install.log"; then
        ((upload_count++))
    fi
    
    if upload_file "temp_npm_test.log" "s3://$bucket_name/reports/$customer_key/npm/temp_npm_test.log"; then
        ((upload_count++))
    fi
    
    log_info "NPM: Uploaded $upload_count files"
}

# Function to process NuGet results
process_nuget_results() {
    local customer_key="$1"
    local bucket_name="$2"
    
    log_info "Processing NuGet results..."
    
    local upload_count=0
    
    # Upload NuGet-specific files
    if upload_file "graviton_compatibility_dotnet.xlsx" "s3://$bucket_name/reports/$customer_key/nuget/graviton_compatibility_dotnet.xlsx"; then
        ((upload_count++))
    fi
    
    # This file might not always be generated, so we check but don't fail if missing
    if upload_file "dotnet_compatibility_results.xlsx" "s3://$bucket_name/reports/$customer_key/nuget/dotnet_compatibility_results.xlsx"; then
        ((upload_count++))
    fi
    
    log_info "NuGet: Uploaded $upload_count files"
}

# Main function
main() {
    log_info "Starting SBOM Graviton Compatibility Analysis Build Setup"
    
    # Validate required environment variables
    if [ -z "$BUCKET_NAME" ] || [ -z "$FILE_KEY" ] || [ -z "$PACKAGE_TYPE" ]; then
        log_error "Required environment variables not set:"
        log_error "BUCKET_NAME: ${BUCKET_NAME:-'NOT SET'}"
        log_error "FILE_KEY: ${FILE_KEY:-'NOT SET'}"
        log_error "PACKAGE_TYPE: ${PACKAGE_TYPE:-'NOT SET'}"
        exit 1
    fi
    
    # Source build-setup.sh to get access to installation functions
    if [ -f "./build-setup.sh" ]; then
        source ./build-setup.sh
        # Install any missing environments based on package type
        install_missing_environments "$PACKAGE_TYPE"
    else
        log_warning "build-setup.sh not found, skipping on-demand environment setup"
    fi
    
    # Display environment information
    log_info "=== Environment Variables ==="
    log_info "BUCKET_NAME=$BUCKET_NAME"
    log_info "FILE_KEY=$FILE_KEY"
    log_info "PACKAGE_TYPE=$PACKAGE_TYPE"
    
    # Extract file name and customer key
    FILE_NAME=$(echo "$FILE_KEY" | awk -F '/' '{print $NF}')
    CUSTOMER_KEY=$(echo "$FILE_NAME" | awk -F '.' '{print $1}')
    
    log_info "FILE_NAME=$FILE_NAME"
    log_info "CUSTOMER_KEY=$CUSTOMER_KEY"
    
    # Download SBOM file
    log_info "=== Downloading SBOM file ==="
    if ! aws s3 cp "s3://$BUCKET_NAME/$FILE_KEY" "$FILE_NAME"; then
        log_error "Failed to download SBOM file from S3"
        exit 1
    fi
    log_success "SBOM file downloaded successfully"
    
    # Process package types
    log_info "=== Processing package types ==="
    
    if [[ "$PACKAGE_TYPE" == *","* ]]; then
        log_info "Multiple package types detected: $PACKAGE_TYPE"
        
        # Process each package type
        for pkg_type in $(echo "$PACKAGE_TYPE" | tr ',' ' '); do
            log_info "Processing package type: $pkg_type"
            
            if ! python3 main.py "$pkg_type" "$FILE_NAME"; then
                log_error "Failed to process package type: $pkg_type"
                continue
            fi
            
            log_success "Completed processing $pkg_type"
        done
    else
        log_info "Single package type detected: $PACKAGE_TYPE"
        
        if ! python3 main.py "$PACKAGE_TYPE" "$FILE_NAME"; then
            log_error "Failed to process package type: $PACKAGE_TYPE"
            log_error "Build setup failed during processing phase"
            exit 1
        fi
        
        log_success "Completed processing $PACKAGE_TYPE"
    fi
    
    # List generated files
    log_info "=== Listing generated files ==="
    find . -type f \( -name "*.xlsx" -o -name "*.md" -o -name "*.txt" -o -name "*.log" \) | head -20
    
    # Upload results to S3
    log_info "=== Uploading results to S3 ==="
    
    local total_uploads=0
    
    if [[ "$PACKAGE_TYPE" == *","* ]]; then
        # Process multiple package types
        for pkg_type in $(echo "$PACKAGE_TYPE" | tr ',' ' '); do
            log_info "Uploading results for package type: $pkg_type"
            
            case "$pkg_type" in
                "maven")
                    process_maven_results "$CUSTOMER_KEY" "$BUCKET_NAME"
                    ;;
                "pip")
                    process_pip_results "$CUSTOMER_KEY" "$BUCKET_NAME"
                    ;;
                "npm")
                    process_npm_results "$CUSTOMER_KEY" "$BUCKET_NAME"
                    ;;
                "nuget")
                    process_nuget_results "$CUSTOMER_KEY" "$BUCKET_NAME"
                    ;;
                *)
                    log_warning "Unknown package type: $pkg_type"
                    ;;
            esac
        done
    else
        # Process single package type
        log_info "Uploading results for single package type: $PACKAGE_TYPE"
        
        case "$PACKAGE_TYPE" in
            "maven")
                process_maven_results "$CUSTOMER_KEY" "$BUCKET_NAME"
                ;;
            "pip")
                process_pip_results "$CUSTOMER_KEY" "$BUCKET_NAME"
                ;;
            "npm")
                process_npm_results "$CUSTOMER_KEY" "$BUCKET_NAME"
                ;;
            "nuget")
                process_nuget_results "$CUSTOMER_KEY" "$BUCKET_NAME"
                ;;
            *)
                log_warning "Unknown package type: $PACKAGE_TYPE"
                ;;
        esac
    fi
    
    # Final file listing
    log_info "=== Final file listing ==="
    ls -la
    
    log_success "Build setup completed successfully!"
    
    # Explicitly exit with success status
    exit 0
}

# Execute main function and handle any unexpected errors
if ! main "$@"; then
    log_error "Build setup failed with an unexpected error"
    exit 1
fi