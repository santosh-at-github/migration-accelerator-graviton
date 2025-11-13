#!/bin/bash

# SBOM Graviton App Dependency Compatibility Tool - Build Setup Script
# This script handles the installation phase from buildspec.yml

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

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to install Python dependencies
setup_python_environment() {
    log_info "=== Setting up Python environment ==="
    
    # Check Python version
    python3 --version
    
    # Install Python dependencies
    log_info "Installing Python dependencies..."
    if ! pip3 install -r requirements.txt; then
        log_error "Failed to install Python dependencies"
        return 1
    fi
    
    log_success "Python environment setup completed successfully"
    return 0
}

# Function to install Java and Maven
setup_java_environment() {
    log_info "=== Setting up Java/Maven environment ==="
    
    # Check Java version
    java -version
    
    # Install Maven
    log_info "Installing Maven..."
    if ! wget https://dlcdn.apache.org/maven/maven-3/3.9.11/source/apache-maven-3.9.11-src.tar.gz; then
        log_error "Failed to download Maven"
        return 1
    fi
    
    if ! tar -xf apache-maven-3.9.11-src.tar.gz; then
        log_error "Failed to extract Maven"
        return 1
    fi
    
    if ! mv apache-maven-3.9.11 /opt/; then
        log_error "Failed to move Maven to /opt/"
        return 1
    fi
    
    # Set up Maven environment
    export M2_HOME='/opt/apache-maven-3.9.11'
    export PATH="$M2_HOME/bin:$PATH"
    
    # Verify Maven installation
    mvn -version
    
    log_success "Java/Maven environment setup completed successfully"
    return 0
}

# Function to install Node.js and NPM
setup_nodejs_environment() {
    log_info "=== Setting up Node.js/NPM environment ==="
    
    # Check if Node.js is already installed
    if command -v node &> /dev/null; then
        log_info "Node.js already installed: $(node --version)"
    else
        log_info "Installing Node.js..."
        # Install Node.js using NodeSource repository - secure approach
        TEMP_SCRIPT=$(mktemp)
        curl -fsSL https://rpm.nodesource.com/setup_18.x -o "$TEMP_SCRIPT"
        # Execute the downloaded script
        bash "$TEMP_SCRIPT"
        rm -f "$TEMP_SCRIPT"
        yum install -y nodejs
    fi
    
    # Check NPM version
    npm --version
    
    log_success "Node.js/NPM environment setup completed successfully"
    return 0
}

# Function to install .NET
setup_dotnet_environment() {
    log_info "=== Setting up .NET environment ==="
    
    # Check if .NET is already installed
    if command -v dotnet &> /dev/null; then
        log_info ".NET already installed: $(dotnet --version)"
    else
        log_info "Installing .NET..."
        # Install .NET 6.0 (LTS)
        rpm -Uvh https://packages.microsoft.com/config/centos/7/packages-microsoft-prod.rpm
        yum install -y dotnet-sdk-6.0
    fi
    
    # Verify .NET installation
    dotnet --version
    
    log_success ".NET environment setup completed successfully"
    return 0
}

# Function to setup build environment based on package types
setup_build_environment() {
    log_info "=== Setting up build environment ==="
    
    # Display basic environment information
    echo "Building dependencies for package types: $PACKAGE_TYPE"
    env | grep -E "(PACKAGE_TYPE|BUCKET_NAME|FILE_KEY)"
    cat /etc/os-release
    
    # Check if PACKAGE_TYPE is set
    if [ -z "$PACKAGE_TYPE" ]; then
        log_error "PACKAGE_TYPE environment variable not set"
        return 1
    fi
    
    # Always install Python dependencies (required for the analysis scripts)
    if ! setup_python_environment; then
        log_error "Failed to setup Python environment"
        return 1
    fi
    
    # Install specific environments based on package types
    if [[ "$PACKAGE_TYPE" == *"maven"* ]]; then
        log_info "Maven package type detected, setting up Java/Maven environment"
        if ! setup_java_environment; then
            log_error "Failed to setup Java/Maven environment"
            return 1
        fi
    fi
    
    if [[ "$PACKAGE_TYPE" == *"npm"* ]]; then
        log_info "NPM package type detected, setting up Node.js/NPM environment"
        if ! setup_nodejs_environment; then
            log_error "Failed to setup Node.js/NPM environment"
            return 1
        fi
    fi
    
    if [[ "$PACKAGE_TYPE" == *"nuget"* ]]; then
        log_info "NuGet package type detected, setting up .NET environment"
        if ! setup_dotnet_environment; then
            log_error "Failed to setup .NET environment"
            return 1
        fi
    fi
    
    # pip packages don't need additional setup beyond Python
    if [[ "$PACKAGE_TYPE" == *"pip"* ]]; then
        log_info "pip package type detected, Python environment already configured"
    fi
    
    log_success "Build environment setup completed successfully"
    return 0
}

# Main function
main() {
    log_info "Starting SBOM Graviton Build Setup (Install Phase)"
    
    # Check if PACKAGE_TYPE is available
    if [ -z "$PACKAGE_TYPE" ]; then
        log_warning "PACKAGE_TYPE not set during install phase"
        log_info "Installing all environments as fallback (will be optimized in future)"
        
        # Fallback: install all environments
        log_info "Setting up Python environment (always required)..."
        if ! setup_python_environment; then
            log_error "Failed to setup Python environment"
            exit 1
        fi
        
        log_info "Setting up Java/Maven environment (fallback)..."
        if ! setup_java_environment; then
            log_error "Failed to setup Java/Maven environment"
            exit 1
        fi
        
        log_warning "Skipping Node.js and .NET installation in fallback mode"
        log_info "These will be installed on-demand if needed during build phase"
    else
        # Setup build environment based on package types
        if ! setup_build_environment; then
            log_error "Build environment setup failed"
            exit 1
        fi
    fi
    
    log_success "Build setup (install phase) completed successfully!"
    exit 0
}

# Function to install missing environments on-demand (can be called from other scripts)
install_missing_environments() {
    local package_type="$1"
    
    if [ -z "$package_type" ]; then
        log_error "Package type not provided to install_missing_environments"
        return 1
    fi
    
    log_info "Checking and installing missing environments for: $package_type"
    
    if [[ "$package_type" == *"maven"* ]]; then
        if ! command -v mvn &> /dev/null; then
            log_info "Maven not found, installing Java/Maven environment"
            setup_java_environment
        else
            log_info "Maven already available: $(mvn -version | head -1)"
        fi
    fi
    
    if [[ "$package_type" == *"npm"* ]]; then
        if ! command -v npm &> /dev/null; then
            log_info "NPM not found, installing Node.js/NPM environment"
            setup_nodejs_environment
        else
            log_info "NPM already available: $(npm --version)"
        fi
    fi
    
    if [[ "$package_type" == *"nuget"* ]]; then
        if ! command -v dotnet &> /dev/null; then
            log_info ".NET not found, installing .NET environment"
            setup_dotnet_environment
        else
            log_info ".NET already available: $(dotnet --version)"
        fi
    fi
    
    return 0
}

# Check if script is being called directly or sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Script is being executed directly
    if ! main "$@"; then
        log_error "Build setup failed with an unexpected error"
        exit 1
    fi
fi