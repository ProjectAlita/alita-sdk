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
PATTERNS=()
VERBOSE=""
DO_SETUP=false
DO_SEED=false
DO_CLEANUP=false
LOCAL_MODE=false
USE_WILDCARDS=false
ENV_FILE=".env"
TIMEOUT=""
TIMEOUT_SET=false
SESSION_ID=""

print_usage() {
    echo "Usage: $0 [OPTIONS] <suite> [pattern1] [pattern2] ..."
    echo ""
    echo "Run individual test(s) within a suite by pattern matching."
    echo ""
    echo "Arguments:"
    echo "  suite              Suite folder name (e.g., github_toolkit)"
    echo "  pattern1 ...       Test name pattern(s) to match (optional if using --pattern flags)"
    echo ""
    echo "Options:"
    echo "  --setup            Run setup before testing (creates toolkit, etc.)"
    echo "  --seed             Seed pipelines before running (required first time)"
    echo "  --cleanup          Run cleanup after testing"
    echo "  --all              Equivalent to --setup --seed --cleanup (full workflow)"
    echo "  --local            Run tests locally without backend (isolated mode)"
    echo "  --wildcards, -w    Use shell-style wildcards in patterns (*, ?)"
    echo "  --pattern PATTERN  Pattern to match (can be repeated)"
    echo "  --env-file FILE    Environment file to use (default: .env)"
    echo "  --timeout SEC      Execution timeout per pipeline (default: 120)"
    echo "  --session-id ID    Session ID for parallel isolation (auto-generated with --all/--setup)"
    echo "  -v, --verbose      Enable verbose output"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  # First time: setup + seed + run"
    echo "  $0 --setup --seed github_toolkit update_file"
    echo ""
    echo "  # Run multiple tests by ID"
    echo "  $0 --all suites/xray XR08 XR09 XR10"
    echo "  $0 -v github_toolkit GH14 GH15 GH16"
    echo ""
    echo "  # Iterative development: just run (after setup/seed done)"
    echo "  $0 github_toolkit update_file"
    echo "  $0 github_toolkit 'GH14'           # Match by name prefix"
    echo "  $0 github_toolkit 'multiline'      # Partial match"
    echo ""
    echo "  # Run with multiple patterns (wildcards)"
    echo "  $0 --all -w github_toolkit --pattern 'GH1[0-9]' --pattern 'GH2*'"
    echo ""
    echo "  # Run multiple tests by listing patterns as arguments"
    echo "  $0 -v --local suites/postman pst01 pst02 pst03  # Runs 3 tests: pst01, pst02, pst03"
    echo "  $0 github_toolkit GH01 GH02 GH03                # Runs 3 tests matching these patterns"
    echo ""
    echo "  # Run all tests in suite (requires --pattern or test name)"
    echo "  $0 --local suites/postman '*'                   # Runs all tests (wildcard)"
    echo "  # $0 --local suites/postman                     # ❌ ERROR: pattern required"
    echo ""
    echo "  # Full workflow for single test"
    echo "  $0 --all github_toolkit update_file"
    echo ""
    echo "  # Re-seed and run (after modifying test YAML)"
    echo "  $0 --seed github_toolkit update_file"
    echo ""
    echo "  # Run locally without backend"
    echo "  $0 --local github_toolkit update_file"
    echo ""
    echo "Note:"
    echo "  - Multiple patterns can be specified as positional args (space-separated)"
    echo "  - At least ONE pattern is always required (use '*' for all tests)"
    echo "  - Local mode (--local) doesn't require setup/seed, runs tests directly"
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
        --local)
            LOCAL_MODE=true
            shift
            ;;
        --wildcards|-w)
            USE_WILDCARDS=true
            shift
            ;;
        --pattern)
            PATTERNS+=("$2")
            shift 2
            ;;
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            TIMEOUT_SET=true
            shift 2
            ;;
        --session-id|--sid)
            SESSION_ID="$2"
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

# ============================================================================
# Parse suite and pattern(s) from positional arguments
# ============================================================================
# Examples of how patterns are parsed:
#
#   Command: run_test.sh -v --local suites/postman pst01 pst02 pst03
#   Result:  SUITE="suites/postman", PATTERNS=("pst01" "pst02" "pst03")
#            → Runs 3 tests matching pst01, pst02, pst03
#
#   Command: run_test.sh -v --local suites/postman
#   Result:  ERROR - Pattern required (at least one pattern must be provided)
#
#   Command: run_test.sh --local suites/postman '*'
#   Result:  SUITE="suites/postman", PATTERNS=("*")
#            → Runs ALL tests in the suite (wildcard match)
#
#   Command: run_test.sh suites/postman --pattern pst01 --pattern pst02
#   Result:  SUITE="suites/postman", PATTERNS=("pst01" "pst02")
#            → Same as positional: runs both pst01 and pst02
# ============================================================================

# Parse suite and optional pattern(s)(s) from positional args
if [ $# -lt 1 ]; then
    echo -e "${RED}Error: Suite argument required${NC}"
    print_usage
    exit 1
fi

SUITE="$1"
shift  # Remove suite from positional args

# If positional patterns provided and no --pattern flags, use all positional args as patterns
if [ $# -gt 0 ] && [ ${#PATTERNS[@]} -eq 0 ]; then
    # Add all remaining positional args as patterns
    while [ $# -gt 0 ]; do
        PATTERNS+=("$1")
        shift
    done
elif [ $# -eq 0 ] && [ ${#PATTERNS[@]} -eq 0 ]; then
    echo -e "${RED}Error: Pattern required (either as argument or via --pattern flag)${NC}\n"
    print_usage
    exit 1
fi

# Build display pattern for logging
if [ ${#PATTERNS[@]} -eq 1 ]; then
    PATTERN="${PATTERNS[0]}"
else
    PATTERN="$(IFS=', '; echo "${PATTERNS[*]}")"
fi

# Validate suite exists
if [ ! -d "$SUITE" ]; then
    echo -e "${RED}Error: Suite directory not found: $SUITE${NC}"
    exit 1
fi

if [ ! -f "$SUITE/pipeline.yaml" ]; then
    echo -e "${RED}Error: pipeline.yaml not found in $SUITE/${NC}"
    exit 1
fi

# Auto-generate session ID for parallel isolation when running full workflow
# Session ID scopes all resources (toolkits, pipelines, env file) to this run
if [ -z "$SESSION_ID" ] && { [ "$DO_SETUP" = true ] || [ "$DO_SEED" = true ] && [ "$DO_CLEANUP" = true ]; }; then
    SESSION_ID=$(python -c "import uuid; print(uuid.uuid4().hex[:8])")
fi

# Scope env file to session if session ID is set
if [ -n "$SESSION_ID" ] && [ "$ENV_FILE" = ".env" ]; then
    ENV_FILE=".env.${SESSION_ID}"
fi

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Running Test: $PATTERN${NC}"
echo -e "${BLUE}  Suite: $SUITE${NC}"
if [ "$LOCAL_MODE" = true ]; then
    echo -e "${BLUE}  Mode: LOCAL (no backend)${NC}"
else
    echo -e "${BLUE}  Mode: REMOTE (backend API)${NC}"
fi
if [ -n "$SESSION_ID" ]; then
    echo -e "${BLUE}  Session: $SESSION_ID${NC}"
    echo -e "${BLUE}  Env File: $ENV_FILE${NC}"
fi
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Build flags for scripts
LOCAL_FLAG=""
if [ "$LOCAL_MODE" = true ]; then
    LOCAL_FLAG="--local"
fi

WILDCARDS_FLAG=""
if [ "$USE_WILDCARDS" = true ]; then
    WILDCARDS_FLAG="--wildcards"
fi

# Build session ID flag
SESSION_FLAG=""
if [ -n "$SESSION_ID" ]; then
    SESSION_FLAG="--session-id $SESSION_ID"
fi

# Step 1: Setup (optional)
if [ "$DO_SETUP" = true ]; then
    echo -e "${YELLOW}▶ Running setup...${NC}"
    if python scripts/setup.py "$SUITE" $VERBOSE --output-env "$ENV_FILE" $LOCAL_FLAG $SESSION_FLAG; then
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
    
    # Build pattern arguments
    PATTERN_ARGS=()
    for p in "${PATTERNS[@]}"; do
        PATTERN_ARGS+=("--pattern" "$p")
    done
    
    if python scripts/seed_pipelines.py "$SUITE" --env-file "$ENV_FILE" "${PATTERN_ARGS[@]}" $VERBOSE $LOCAL_FLAG $WILDCARDS_FLAG $SESSION_FLAG; then
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

# Build timeout argument - only pass if user explicitly provided it
# Otherwise, run_suite.py will read from config or use its default (120)
TIMEOUT_ARG=""
if [ "$TIMEOUT_SET" = true ]; then
    TIMEOUT_ARG="--timeout $TIMEOUT"
fi

# Build pattern arguments (same as for seeding)
PATTERN_ARGS=()
for p in "${PATTERNS[@]}"; do
    PATTERN_ARGS+=("--pattern" "$p")
done

# Run with pattern filter
RESULTS_FILE="test_results/$SUITE/results.json"
if python scripts/run_suite.py "$SUITE" \
    "${PATTERN_ARGS[@]}" \
    $TIMEOUT_ARG \
    --env-file "$ENV_FILE" \
    --output-json "$RESULTS_FILE" \
    $VERBOSE \
    $LOCAL_FLAG \
    $WILDCARDS_FLAG \
    $SESSION_FLAG; then

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
    if python scripts/cleanup.py "$SUITE" --yes $VERBOSE --env-file "$ENV_FILE" $LOCAL_FLAG $SESSION_FLAG; then
        # Clean up session-scoped env file
        if [ -n "$SESSION_ID" ] && [ -f "$ENV_FILE" ] && [[ "$ENV_FILE" == *".${SESSION_ID}" ]]; then
            rm -f "$ENV_FILE"
        fi
        echo -e "${GREEN}✓ Cleanup completed${NC}"
    else
        echo -e "${RED}✗ Cleanup failed (continuing)${NC}"
    fi
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"

# Parse results and display summary
if [ -f "$RESULTS_FILE" ]; then
    PASSED=$(python -c "import json; data=json.load(open('$RESULTS_FILE')); print(data.get('passed', 0))" 2>/dev/null || echo "0")
    FAILED=$(python -c "import json; data=json.load(open('$RESULTS_FILE')); print(data.get('failed', 0))" 2>/dev/null || echo "0")
    ERRORS=$(python -c "import json; data=json.load(open('$RESULTS_FILE')); print(data.get('errors', 0))" 2>/dev/null || echo "0")
    SKIPPED=$(python -c "import json; data=json.load(open('$RESULTS_FILE')); print(data.get('skipped', 0))" 2>/dev/null || echo "0")
    TOTAL=$(python -c "import json; data=json.load(open('$RESULTS_FILE')); print(data.get('total', 0))" 2>/dev/null || echo "0")

    echo -e "${BLUE}Test Results Summary:${NC}"
    echo "  Passed:  $PASSED"
    echo "  Failed:  $FAILED"
    echo "  Errors:  $ERRORS"
    echo "  Skipped: $SKIPPED"
    echo "  Total:   $TOTAL"
    echo ""

    # Determine overall success
    if [ "$FAILED" -gt 0 ] || [ "$ERRORS" -gt 0 ]; then
        echo -e "${RED}✗ Some tests failed or had errors${NC}"
        echo "Results saved to: $RESULTS_FILE"
        exit 1
    elif [ "$RUN_STATUS" -ne 0 ]; then
        echo -e "${RED}✗ Test execution failed${NC}"
        exit $RUN_STATUS
    else
        echo -e "${GREEN}✓ All tests passed!${NC}"
        echo "Results saved to: $RESULTS_FILE"
        exit 0
    fi
else
    # No results file - use RUN_STATUS from execution
    if [ "$RUN_STATUS" -eq 0 ]; then
        echo -e "${GREEN}✓ Test execution completed${NC}"
        exit 0
    else
        echo -e "${RED}✗ Test execution failed${NC}"
        exit $RUN_STATUS
    fi
fi
