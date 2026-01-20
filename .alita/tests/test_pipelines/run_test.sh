#!/usr/bin/env bash

# run_test.sh
# Run individual test(s) within a suite - useful for development and debugging

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Defaults
SUITE=""
PATTERN=""
VERBOSE=""
DO_SETUP=false
DO_SEED=false
DO_CLEANUP=false
ENV_FILE=".env"
TIMEOUT=120

print_usage() {
    echo "Usage: $0 [OPTIONS] <suite> <pattern>"
    echo ""
    echo "Run individual test(s) within a suite by pattern matching."
    echo ""
    echo "Arguments:"
    echo "  suite              Suite folder name (e.g., github_toolkit)"
    echo "  pattern            Test name pattern to match (e.g., 'update_file', 'GH14')"
    echo ""
    echo "Options:"
    echo "  --setup            Run setup before testing (creates toolkit, etc.)"
    echo "  --seed             Seed pipelines before running (required first time)"
    echo "  --cleanup          Run cleanup after testing"
    echo "  --all              Equivalent to --setup --seed --cleanup (full workflow)"
    echo "  --env-file FILE    Environment file to use (default: .env)"
    echo "  --timeout SEC      Execution timeout per pipeline (default: 120)"
    echo "  -v, --verbose      Enable verbose output"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  # First time: setup + seed + run"
    echo "  $0 --setup --seed github_toolkit update_file"
    echo ""
    echo "  # Iterative development: just run (after setup/seed done)"
    echo "  $0 github_toolkit update_file"
    echo "  $0 github_toolkit 'GH14'           # Match by name prefix"
    echo "  $0 github_toolkit 'multiline'      # Partial match"
    echo ""
    echo "  # Run multiple tests matching pattern"
    echo "  $0 github_toolkit 'GH1'            # Runs GH1, GH10-GH19"
    echo ""
    echo "  # Full workflow for single test"
    echo "  $0 --all github_toolkit update_file"
    echo ""
    echo "  # Re-seed and run (after modifying test YAML)"
    echo "  $0 --seed github_toolkit update_file"
    echo ""
    echo "Workflow:"
    echo "  1. First run:  $0 --setup --seed <suite> <pattern>"
    echo "  2. Iterate:    $0 <suite> <pattern>  (fast, no setup/seed)"
    echo "  3. After YAML changes: $0 --seed <suite> <pattern>"
    echo "  4. Final cleanup: $0 --cleanup <suite> <pattern>"
}

# Parse arguments
POSITIONAL=()
while [[ $# -gt 0 ]]; do
    case $1 in
        --setup)
            DO_SETUP=true
            shift
            ;;
        --seed)
            DO_SEED=true
            shift
            ;;
        --cleanup)
            DO_CLEANUP=true
            shift
            ;;
        --all)
            DO_SETUP=true
            DO_SEED=true
            DO_CLEANUP=true
            shift
            ;;
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE="--verbose"
            shift
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        -*)
            echo -e "${RED}Unknown option: $1${NC}"
            print_usage
            exit 1
            ;;
        *)
            POSITIONAL+=("$1")
            shift
            ;;
    esac
done

# Restore positional parameters
set -- "${POSITIONAL[@]}"

# Validate arguments
if [ $# -lt 2 ]; then
    echo -e "${RED}Error: Missing required arguments${NC}"
    echo ""
    print_usage
    exit 1
fi

SUITE="$1"
PATTERN="$2"

# Validate suite exists
if [ ! -d "$SUITE" ]; then
    echo -e "${RED}Error: Suite directory not found: $SUITE${NC}"
    exit 1
fi

if [ ! -f "$SUITE/pipeline.yaml" ]; then
    echo -e "${RED}Error: pipeline.yaml not found in $SUITE/${NC}"
    exit 1
fi

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Running Test: $PATTERN${NC}"
echo -e "${BLUE}  Suite: $SUITE${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Step 1: Setup (optional)
if [ "$DO_SETUP" = true ]; then
    echo -e "${YELLOW}▶ Running setup...${NC}"
    if python scripts/setup.py "$SUITE" $VERBOSE --output-env "$ENV_FILE"; then
        echo -e "${GREEN}✓ Setup completed${NC}"
    else
        echo -e "${RED}✗ Setup failed${NC}"
        exit 1
    fi
    echo ""
fi

# Check env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}Error: Environment file not found: $ENV_FILE${NC}"
    echo -e "${YELLOW}Hint: Run with --setup first, or specify --env-file${NC}"
    exit 1
fi

# Step 2: Seed (optional)
if [ "$DO_SEED" = true ]; then
    echo -e "${YELLOW}▶ Seeding pipelines matching: '$PATTERN'${NC}"
    if python scripts/seed_pipelines.py "$SUITE" --env-file "$ENV_FILE" --pattern "$PATTERN" $VERBOSE; then
        echo -e "${GREEN}✓ Pipelines seeded${NC}"
    else
        echo -e "${RED}✗ Seeding failed${NC}"
        exit 1
    fi
    echo ""
fi

# Step 3: Run test(s)
echo -e "${YELLOW}▶ Running test(s) matching: '$PATTERN'${NC}"
echo ""

# Load env file for run_suite.py
set -a
source "$ENV_FILE"
set +a

# Run with pattern filter
if python scripts/run_suite.py "$SUITE" \
    --pattern "$PATTERN" \
    --timeout "$TIMEOUT" \
    --env-file "$ENV_FILE" \
    $VERBOSE; then

    RUN_STATUS=0
    echo ""
    echo -e "${GREEN}✓ Test execution completed${NC}"
else
    RUN_STATUS=$?
    echo ""
    echo -e "${RED}✗ Test execution failed${NC}"
fi

# Step 4: Cleanup (optional)
if [ "$DO_CLEANUP" = true ]; then
    echo ""
    echo -e "${YELLOW}▶ Running cleanup...${NC}"
    if python scripts/cleanup.py "$SUITE" --yes $VERBOSE; then
        echo -e "${GREEN}✓ Cleanup completed${NC}"
    else
        echo -e "${RED}✗ Cleanup failed (continuing)${NC}"
    fi
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

exit $RUN_STATUS
