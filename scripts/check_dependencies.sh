#!/bin/bash
# Dependency conflict checking script for alita-sdk
# This script provides comprehensive dependency validation for pyproject.toml

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALITA_SDK_DIR="$PROJECT_ROOT/alita-sdk"

echo "🔍 Dependency Conflict Checker for alita-sdk"
echo "============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command_exists python; then
        log_error "Python is not installed or not in PATH"
        exit 1
    fi
    
    if ! command_exists pip; then
        log_error "pip is not installed or not in PATH"
        exit 1
    fi
    
    log_info "Python version: $(python --version)"
    log_info "pip version: $(pip --version)"
}

# Create clean test environment
create_test_env() {
    local env_name="$1"
    local env_path="$ALITA_SDK_DIR/$env_name"
    
    log_info "Creating clean test environment: $env_name"
    
    if [ -d "$env_path" ]; then
        log_warn "Removing existing test environment"
        rm -rf "$env_path"
    fi
    
    python -m venv "$env_path"
    source "$env_path/bin/activate"
    
    # Upgrade pip and install pip-tools
    pip install --upgrade pip
    pip install pip-tools
    
    log_info "Test environment created at: $env_path"
}

# Run pip-compile to check for conflicts
check_with_pip_compile() {
    local extras="$1"
    log_info "Running pip-compile for extras: [$extras]"
    
    cd "$ALITA_SDK_DIR"
    
    # Create temporary requirements file
    local temp_req_file="temp_requirements.in"
    echo "-e .[${extras}]" > "$temp_req_file"
    
    # Run pip-compile with dry-run
    if pip-compile "$temp_req_file" --dry-run --no-emit-index-url --verbose 2>&1; then
        log_info "✅ No conflicts found for extras: [$extras]"
    else
        log_error "❌ Conflicts detected for extras: [$extras]"
        rm -f "$temp_req_file"
        return 1
    fi
    
    rm -f "$temp_req_file"
}

# Run pip install simulation
simulate_install() {
    local extras="$1"
    log_info "Simulating installation for extras: [$extras]"
    
    cd "$ALITA_SDK_DIR"
    
    if pip install -e ".[${extras}]" --dry-run 2>&1 | grep -q "ERROR\|conflict\|incompatible"; then
        log_error "❌ Installation simulation failed for extras: [$extras]"
        return 1
    else
        log_info "✅ Installation simulation passed for extras: [$extras]"
    fi
}

# Check specific extras groups
check_extras_groups() {
    local groups=("runtime" "tools" "community" "dev" "all")
    
    for group in "${groups[@]}"; do
        log_info "Checking extras group: $group"
        
        if ! check_with_pip_compile "$group"; then
            log_error "pip-compile check failed for: $group"
            return 1
        fi
        
        if ! simulate_install "$group"; then
            log_error "Installation simulation failed for: $group"
            return 1
        fi
        
        log_info "✅ Group '$group' passed all checks"
        echo ""
    done
}

# Use pipdeptree for dependency analysis (if available)
analyze_with_pipdeptree() {
    if command_exists pipdeptree; then
        log_info "Running pipdeptree analysis..."
        
        # Install the package first
        cd "$ALITA_SDK_DIR"
        pip install -e ".[runtime]" --quiet
        
        # Check for conflicts
        if pipdeptree --warn fail; then
            log_info "✅ No dependency conflicts detected by pipdeptree"
        else
            log_warn "⚠️ Potential conflicts detected by pipdeptree"
        fi
        
        # Show dependency tree
        log_info "Dependency tree for alita-sdk:"
        pipdeptree -p alita-sdk
    else
        log_warn "pipdeptree not available, skipping tree analysis"
        log_info "Install with: pip install pipdeptree"
    fi
}

# Main execution
main() {
    check_prerequisites
    
    # Create and activate test environment
    create_test_env "dep_check_env"
    source "$ALITA_SDK_DIR/dep_check_env/bin/activate"
    
    # Run all checks
    log_info "Starting comprehensive dependency checks..."
    echo ""
    
    check_extras_groups
    analyze_with_pipdeptree
    
    log_info "🎉 All dependency checks completed successfully!"
    log_info "Your pyproject.toml appears to be free of dependency conflicts."
    
    # Cleanup
    deactivate
    log_info "Cleaning up test environment..."
    rm -rf "$ALITA_SDK_DIR/dep_check_env"
}

# Handle script arguments
case "${1:-}" in
    "runtime"|"tools"|"community"|"dev"|"all")
        check_prerequisites
        create_test_env "dep_check_env"
        source "$ALITA_SDK_DIR/dep_check_env/bin/activate"
        check_with_pip_compile "$1"
        simulate_install "$1"
        deactivate
        rm -rf "$ALITA_SDK_DIR/dep_check_env"
        ;;
    "help"|"--help"|"-h")
        echo "Usage: $0 [extras_group]"
        echo ""
        echo "Options:"
        echo "  runtime     Check only runtime dependencies"
        echo "  tools       Check only tools dependencies"
        echo "  community   Check only community dependencies"
        echo "  dev         Check only dev dependencies"
        echo "  all         Check all dependencies"
        echo "  help        Show this help message"
        echo ""
        echo "If no argument is provided, all groups will be checked."
        ;;
    "")
        main
        ;;
    *)
        log_error "Unknown argument: $1"
        echo "Use '$0 help' for usage information."
        exit 1
        ;;
esac