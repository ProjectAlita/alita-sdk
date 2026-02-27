#!/usr/bin/env bash

# run_all_suites.sh
# Execute all test suites sequentially with setup, seed, run, and cleanup

# Check bash version (requires 4.0+ for associative arrays)
if [ "${BASH_VERSINFO[0]}" -lt 4 ]; then
    echo "Error: This script requires bash 4.0 or higher"
    echo "Current bash version: ${BASH_VERSION}"
    echo ""
    echo "On macOS, install bash 4+ with: brew install bash"
    echo "Then run with: /usr/local/bin/bash $0 $@"
    echo "Or run with: bash $0 $@  (if bash 4+ is in PATH)"
    exit 1
fi

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Default suites to run
DEFAULT_SUITES=("github_toolkit" "state_retrieval" "structured_output")

# Parse arguments
SUITES=()
VERBOSE=""
SHOW_OUTPUT=false
SKIP_CLEANUP=false
SKIP_SETUP=false
SKIP_INITIAL_CLEANUP=false
STOP_ON_FAILURE=false
LOCAL_MODE=false
ENABLE_PARALLEL=true
OUTPUT_DIR="test_results"

print_usage() {
    echo "Usage: $0 [OPTIONS] [SUITE...]"
    echo ""
    echo "Run test suites with full workflow (setup, seed, run, cleanup)"
    echo ""
    echo "Options:"
    echo "  -v, --verbose           Enable verbose output with real-time display"
    echo "  --local                 Run tests locally without backend (isolated mode)"
    echo "  --parallel              Enable parallel test execution (uses value from pipeline.yaml)"
    echo "  --no-parallel           Disable parallel execution (forces sequential)"
    echo "  --skip-initial-cleanup  Skip cleanup before starting (not recommended)"
    echo "  --skip-cleanup          Skip cleanup after tests"
    echo "  --skip-setup            Skip setup (use existing environment)"
    echo "  --stop-on-failure       Stop executing suites if one fails"
    echo "  -o, --output DIR        Output directory for results (default: test_results)"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Suites:"
    echo "  If no suites specified, runs all: ${DEFAULT_SUITES[*]}"
    echo "  Available suites: github_toolkit, state_retrieval, structured_output"
    echo ""
    echo "Suite Specification Format:"
    echo "  'suite_name'                    - Uses default pipeline.yaml"
    echo "  'suite_name:pipeline_file.yaml' - Uses specific pipeline config file"
    echo ""
    echo "Examples:"
    echo "  $0                              # Run all suites with initial cleanup"
    echo "  $0 -v github_toolkit            # Run GitHub toolkit with verbose output"
    echo "  $0 -v                           # Run all suites with verbose real-time output"
    echo "  $0 --local github_toolkit       # Run GitHub toolkit locally (no backend)"
    echo "  $0 --skip-cleanup               # Run all but skip post-test cleanup"
    echo "  $0 --skip-initial-cleanup       # Skip cleanup before starting"
    echo "  $0 --stop-on-failure state_retrieval structured_output"
    echo "  $0 github_toolkit_negative:pipeline_validation.yaml  # Run specific pipeline config"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE="--verbose"
            SHOW_OUTPUT=true
            shift
            ;;
        --local)
            LOCAL_MODE=true
            LOCAL_LOG_LEVEL=""
            shift
            # Check if next argument is a log level (not a suite name or option)
            if [[ "$1" =~ ^(debug|info|warning|error)$ ]]; then
                LOCAL_LOG_LEVEL="=$1"
                shift
            fi
            ;;
        --local=*)
            LOCAL_MODE=true
            LOCAL_LOG_LEVEL="=${1#*=}"
            shift
            ;;
        --parallel)
            ENABLE_PARALLEL=true
            shift
            ;;
        --no-parallel)
            ENABLE_PARALLEL=false
            shift
            ;;
        --skip-initial-cleanup)
            SKIP_INITIAL_CLEANUP=true
            shift
            ;;
        --skip-cleanup)
            SKIP_CLEANUP=true
            shift
            ;;
        --skip-setup)
            SKIP_SETUP=true
            shift
            ;;
        --stop-on-failure)
            STOP_ON_FAILURE=true
            shift
            ;;
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            SUITES+=("$1")
            shift
            ;;
    esac
done

# Use default suites if none specified
if [ ${#SUITES[@]} -eq 0 ]; then
    SUITES=("${DEFAULT_SUITES[@]}")
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Generate session ID for parallel execution isolation
SESSION_ID=$(python -c "import uuid; print(uuid.uuid4().hex[:8])")
ENV_FILE=".env.${SESSION_ID}"
SESSION_FLAG="--session-id $SESSION_ID"

# Summary tracking
declare -A SUITE_RESULTS
declare -A SUITE_PASSED
declare -A SUITE_FAILED
declare -A SUITE_ERRORS
declare -A SUITE_SKIPPED
declare -A SUITE_DURATION
TOTAL_START=$(date +%s)

print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_step() {
    echo -e "${YELLOW}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

run_suite() {
    local suite_spec=$1
    local suite_start=$(date +%s)

    # Parse suite specification: 'folder' or 'folder:pipeline_file.yaml'
    local suite_dir
    local pipeline_file
    if [[ "$suite_spec" == *":"* ]]; then
        suite_dir="${suite_spec%%:*}"
        pipeline_file="${suite_spec#*:}"
    else
        suite_dir="$suite_spec"
        pipeline_file=""
    fi

    print_header "Running Test Suite: $suite_spec"

    # Check if suite directory exists
    if [ ! -d "$suite_dir" ]; then
        print_error "Suite directory not found: $suite_dir"
        SUITE_RESULTS["$suite_spec"]="FAILED"
        return 1
    fi

    # Check if pipeline config exists
    local config_file="${pipeline_file:-pipeline.yaml}"
    if [ ! -f "$suite_dir/$config_file" ]; then
        print_error "$config_file not found in $suite_dir/"
        SUITE_RESULTS["$suite_spec"]="FAILED"
        return 1
    fi

    # Create output directory using sanitized suite name (replace : with _)
    # Strip 'suites/' prefix to avoid duplication in output paths
    local suite_output_name="${suite_spec//:/_}"
    suite_output_name="${suite_output_name#suites/}"
    local suite_output_dir="$OUTPUT_DIR/suites/$suite_output_name"
    mkdir -p "$suite_output_dir"

    # Step 1: Setup
    if [ "$SKIP_SETUP" = false ]; then
        print_step "Step 1/4: Running setup for $suite_spec"
        if [ "$SHOW_OUTPUT" = true ]; then
            # Show output in real-time while also capturing to log
            # Set FORCE_COLOR=1 to preserve colors through tee pipe
            if FORCE_COLOR=1 python scripts/setup.py "$suite_spec" $VERBOSE --output-env "$ENV_FILE" $SESSION_FLAG 2>&1 | tee "$suite_output_dir/setup.log"; then
                print_success "Setup completed"
            else
                print_error "Setup failed - see $suite_output_dir/setup.log"
                SUITE_RESULTS["$suite_spec"]="SETUP_FAILED"
                return 1
            fi
        else
            # Capture to log only
            if python scripts/setup.py "$suite_spec" $VERBOSE --output-env "$ENV_FILE" $SESSION_FLAG > "$suite_output_dir/setup.log" 2>&1; then
                print_success "Setup completed"
            else
                print_error "Setup failed - see $suite_output_dir/setup.log"
                SUITE_RESULTS["$suite_spec"]="SETUP_FAILED"
                cat "$suite_output_dir/setup.log"
                return 1
            fi
        fi
    else
        echo "  Skipping setup (using existing environment)"
    fi

    # Step 2: Seed pipelines
    print_step "Step 2/4: Seeding pipelines for $suite_spec"
    if [ "$SHOW_OUTPUT" = true ]; then
        # Show output in real-time while also capturing to log
        # Set FORCE_COLOR=1 to preserve colors through tee pipe
        if FORCE_COLOR=1 python scripts/seed_pipelines.py "$suite_spec" --env-file "$ENV_FILE" $VERBOSE $SESSION_FLAG 2>&1 | tee "$suite_output_dir/seed.log"; then
            print_success "Pipelines seeded"
        else
            print_error "Seeding failed - see $suite_output_dir/seed.log"
            SUITE_RESULTS["$suite_spec"]="SEED_FAILED"
            return 1
        fi
    else
        # Capture to log only
        if python scripts/seed_pipelines.py "$suite_spec" --env-file "$ENV_FILE" $VERBOSE $SESSION_FLAG > "$suite_output_dir/seed.log" 2>&1; then
            print_success "Pipelines seeded"
        else
            print_error "Seeding failed - see $suite_output_dir/seed.log"
            SUITE_RESULTS["$suite_spec"]="SEED_FAILED"
            cat "$suite_output_dir/seed.log"
            return 1
        fi
    fi

    # Step 3: Run tests
    print_step "Step 3/4: Running tests for $suite_spec"
    local results_file="$suite_output_dir/results.json"

    # Extract timeout from config (will be overridden by run_suite.py if not found)
    # Note: run_suite.py will use config value automatically, no need to pass --timeout
    # unless we want to override it

    # Build parallel flag based on ENABLE_PARALLEL setting
    # If parallel is disabled, force sequential execution with --parallel 1
    # If parallel is enabled, don't pass flag (let run_suite.py read from config)
    PARALLEL_FLAG=""
    if [ "$ENABLE_PARALLEL" = false ]; then
        PARALLEL_FLAG="--parallel 1"
    fi

    # Run tests with JSON output to file via --output-json, verbose to stderr (run.log)
    # Verbose output controlled by $VERBOSE flag (-v)
    if [ "$SHOW_OUTPUT" = true ]; then
        # Show verbose output in real-time while also capturing to log
        # Set FORCE_COLOR=1 to preserve colors through tee pipe
        if FORCE_COLOR=1 python scripts/run_suite.py "$suite_spec" $VERBOSE $PARALLEL_FLAG --env-file "$ENV_FILE" --output-json "$results_file" $SESSION_FLAG 2> >(tee "$suite_output_dir/run.log" >&2); then
            print_success "Tests completed"
        else
            print_error "Test execution failed - see $suite_output_dir/run.log"
            SUITE_RESULTS["$suite_spec"]="RUN_FAILED"
            cat "$suite_output_dir/run.log"
            return 1
        fi
    else
        # Capture verbose output to log file only
        if python scripts/run_suite.py "$suite_spec" $VERBOSE $PARALLEL_FLAG --env-file "$ENV_FILE" --output-json "$results_file" $SESSION_FLAG 2> "$suite_output_dir/run.log"; then
            print_success "Tests completed"
        else
            print_error "Test execution failed - see $suite_output_dir/run.log"
            SUITE_RESULTS["$suite_spec"]="RUN_FAILED"
            cat "$suite_output_dir/run.log"
            return 1
        fi
    fi

    # Parse results
    if [ -f "$results_file" ]; then
        local passed=$(python -c "import json; data=json.load(open('$results_file')); print(data.get('passed', 0))" 2>/dev/null || echo "0")
        local failed=$(python -c "import json; data=json.load(open('$results_file')); print(data.get('failed', 0))" 2>/dev/null || echo "0")
        local errors=$(python -c "import json; data=json.load(open('$results_file')); print(data.get('errors', 0))" 2>/dev/null || echo "0")
        local skipped=$(python -c "import json; data=json.load(open('$results_file')); print(data.get('skipped', 0))" 2>/dev/null || echo "0")
        local total=$(python -c "import json; data=json.load(open('$results_file')); print(data.get('total', 0))" 2>/dev/null || echo "0")

        SUITE_PASSED["$suite_spec"]=$passed
        SUITE_FAILED["$suite_spec"]=$failed
        SUITE_ERRORS["$suite_spec"]=$errors
        SUITE_SKIPPED["$suite_spec"]=$skipped

        echo "  Results: $passed passed, $failed failed, $errors errors, $skipped skipped (total: $total)"

        if [ "$failed" -gt 0 ] || [ "$errors" -gt 0 ]; then
            SUITE_RESULTS["$suite_spec"]="TESTS_FAILED"
            print_error "Some tests failed"
        else
            SUITE_RESULTS["$suite_spec"]="PASSED"
        fi
    else
        print_error "Test execution failed - see $suite_output_dir/run.log"
        SUITE_RESULTS["$suite_spec"]="RUN_FAILED"
        cat "$suite_output_dir/run.log"
        return 1
    fi

    # Create copy for bug reporter + errors-only view for test-fixer agent
    if [ -f "$results_file" ]; then
        cp "$results_file" "${suite_output_dir}/results_for_bug_reporter.json"
        python scripts/results_errors_only.py "$results_file" "${results_file%.json}_errors_only.json" 2>/dev/null || true
        cp "${results_file%.json}_errors_only.json" "${suite_output_dir}/results_errors_only_for_bug_reporter.json" 2>/dev/null || true
    fi

    # Step 4: Cleanup
    if [ "$SKIP_CLEANUP" = false ]; then
        print_step "Step 4/4: Cleaning up $suite_spec"
        if [ "$SHOW_OUTPUT" = true ]; then
            # Show output in real-time while also capturing to log
            if FORCE_COLOR=1 python scripts/cleanup.py "$suite_spec" --yes $VERBOSE --env-file "$ENV_FILE" $SESSION_FLAG 2>&1 | tee "$suite_output_dir/cleanup.log"; then
                # Clean up session-scoped env file
                [ -f "$ENV_FILE" ] && rm -f "$ENV_FILE"
                print_success "Cleanup completed"
            else
                print_error "Cleanup failed - see $suite_output_dir/cleanup.log (continuing anyway)"
                # Don't fail suite on cleanup failure
            fi
        else
            if python scripts/cleanup.py "$suite_spec" --yes $VERBOSE --env-file "$ENV_FILE" $SESSION_FLAG > "$suite_output_dir/cleanup.log" 2>&1; then
                # Clean up session-scoped env file
                [ -f "$ENV_FILE" ] && rm -f "$ENV_FILE"
                print_success "Cleanup completed"
            else
                print_error "Cleanup failed - see $suite_output_dir/cleanup.log (continuing anyway)"
                # Don't fail suite on cleanup failure
            fi
        fi
    else
        echo "  Skipping cleanup"
    fi

    local suite_end=$(date +%s)
    local suite_duration=$((suite_end - suite_start))
    SUITE_DURATION["$suite_spec"]=$suite_duration

    print_success "Suite $suite_spec completed in ${suite_duration}s"

    return 0
}

run_suite_local() {
    # Run suite in local mode (no backend) - same flow as remote
    local suite_spec=$1
    local suite_start=$(date +%s)

    # Parse suite specification: 'folder' or 'folder:pipeline_file.yaml'
    local suite_dir
    local pipeline_file
    if [[ "$suite_spec" == *":"* ]]; then
        suite_dir="${suite_spec%%:*}"
        pipeline_file="${suite_spec#*:}"
    else
        suite_dir="$suite_spec"
        pipeline_file=""
    fi

    print_header "Running Test Suite (LOCAL): $suite_spec"

    # Check if suite directory exists
    if [ ! -d "$suite_dir" ]; then
        print_error "Suite directory not found: $suite_dir"
        SUITE_RESULTS["$suite_spec"]="FAILED"
        return 1
    fi

    # Check if pipeline config exists
    local config_file="${pipeline_file:-pipeline.yaml}"
    if [ ! -f "$suite_dir/$config_file" ]; then
        print_error "$config_file not found in $suite_dir/"
        SUITE_RESULTS["$suite_spec"]="FAILED"
        return 1
    fi

    # Create output directory using sanitized suite name (replace : with _)
    # Strip 'suites/' prefix to avoid duplication in output paths
    local suite_output_name="${suite_spec//:/_}"
    suite_output_name="${suite_output_name#suites/}"
    local suite_output_dir="$OUTPUT_DIR/suites/$suite_output_name"
    mkdir -p "$suite_output_dir"

    # Note: Local mode setup is handled internally by run_suite.py
    # No separate setup step needed - run_suite.py executes setup and runs tests
    
    # Step 1: Run tests (with --local flag, includes internal setup)
    print_step "Step 1/2: Running tests for $suite_spec (local)"
    local results_file="$suite_output_dir/results.json"

    # Build parallel flag based on ENABLE_PARALLEL setting
    # If parallel is disabled, force sequential execution with --parallel 1
    # If parallel is enabled, don't pass flag (let run_suite.py read from config)
    PARALLEL_FLAG=""
    if [ "$ENABLE_PARALLEL" = false ]; then
        PARALLEL_FLAG="--parallel 1"
    fi

    # Save JSON results to file with --output-json, stderr goes to run.log
    # run_suite.py --local executes setup internally and then runs tests
    # Verbose output controlled by $VERBOSE flag (-v)
    if [ "$SHOW_OUTPUT" = true ]; then
        # Show verbose output in real-time while also capturing to log
        # Set FORCE_COLOR=1 to preserve colors through tee pipe
        if FORCE_COLOR=1 python scripts/run_suite.py "$suite_spec" $VERBOSE --local $PARALLEL_FLAG --output-json "$results_file" $SESSION_FLAG 2> >(tee "$suite_output_dir/run.log" >&2); then
            print_success "Tests completed"
        else
            print_error "Test execution failed - see $suite_output_dir/run.log"
            SUITE_RESULTS["$suite_spec"]="RUN_FAILED"
            cat "$suite_output_dir/run.log"
            return 1
        fi
    else
        # Capture verbose output to log file only
        if python scripts/run_suite.py "$suite_spec" $VERBOSE --local $PARALLEL_FLAG --output-json "$results_file" $SESSION_FLAG 2> "$suite_output_dir/run.log"; then
            print_success "Tests completed"
        else
            print_error "Test execution failed - see $suite_output_dir/run.log"
            SUITE_RESULTS["$suite_spec"]="RUN_FAILED"
            cat "$suite_output_dir/run.log"
            return 1
        fi
    fi

    # Parse results
    if [ -f "$results_file" ]; then
        local passed=$(python -c "import json; data=json.load(open('$results_file')); print(data.get('passed', 0))" 2>/dev/null || echo "0")
        local failed=$(python -c "import json; data=json.load(open('$results_file')); print(data.get('failed', 0))" 2>/dev/null || echo "0")
        local errors=$(python -c "import json; data=json.load(open('$results_file')); print(data.get('errors', 0))" 2>/dev/null || echo "0")
        local skipped=$(python -c "import json; data=json.load(open('$results_file')); print(data.get('skipped', 0))" 2>/dev/null || echo "0")
        local total=$(python -c "import json; data=json.load(open('$results_file')); print(data.get('total', 0))" 2>/dev/null || echo "0")

        SUITE_PASSED["$suite_spec"]=$passed
        SUITE_FAILED["$suite_spec"]=$failed
        SUITE_ERRORS["$suite_spec"]=$errors
        SUITE_SKIPPED["$suite_spec"]=$skipped

        echo "  Results: $passed passed, $failed failed, $errors errors, $skipped skipped (total: $total)"

        if [ "$failed" -gt 0 ] || [ "$errors" -gt 0 ]; then
            SUITE_RESULTS["$suite_spec"]="TESTS_FAILED"
            print_error "Some tests failed"
        else
            SUITE_RESULTS["$suite_spec"]="PASSED"
        fi
    fi

    # Create copy for bug reporter + errors-only view for test-fixer agent
    if [ -f "$results_file" ]; then
        cp "$results_file" "${suite_output_dir}/results_for_bug_reporter.json"
        python scripts/results_errors_only.py "$results_file" "${results_file%.json}_errors_only.json" 2>/dev/null || true
        cp "${results_file%.json}_errors_only.json" "${suite_output_dir}/results_errors_only_for_bug_reporter.json" 2>/dev/null || true
    fi

    # Step 3: Cleanup (with --local flag)
    if [ "$SKIP_CLEANUP" = false ]; then
        print_step "Step 3/3: Cleaning up $suite_spec (local)"
        if [ "$SHOW_OUTPUT" = true ]; then
            # Show output in real-time while also capturing to log
            if FORCE_COLOR=1 python scripts/cleanup.py "$suite_spec" --yes $VERBOSE --local $SESSION_FLAG 2>&1 | tee "$suite_output_dir/cleanup.log"; then
                print_success "Cleanup completed"
            else
                print_error "Cleanup failed - see $suite_output_dir/cleanup.log (continuing anyway)"
                # Don't fail suite on cleanup failure
            fi
        else
            if python scripts/cleanup.py "$suite_spec" --yes $VERBOSE --local $SESSION_FLAG > "$suite_output_dir/cleanup.log" 2>&1; then
                print_success "Cleanup completed"
            else
                print_error "Cleanup failed - see $suite_output_dir/cleanup.log (continuing anyway)"
                # Don't fail suite on cleanup failure
            fi
        fi
    else
        echo "  Skipping cleanup"
    fi

    local suite_end=$(date +%s)
    local suite_duration=$((suite_end - suite_start))
    SUITE_DURATION["$suite_spec"]=$suite_duration

    print_success "Suite $suite_spec (LOCAL) completed in ${suite_duration}s"

    return 0
}

# Main execution
print_header "Test Suites Execution"
echo "Suites to run: ${SUITES[*]}"
echo "Output directory: $OUTPUT_DIR"
if [ "$LOCAL_MODE" = true ]; then
    echo "Mode: LOCAL (no backend)"
else
    echo "Mode: REMOTE (backend API)"
fi
echo "Session ID: $SESSION_ID"
echo ""

# Initial cleanup - remove leftover resources from previous runs
if [ "$SKIP_INITIAL_CLEANUP" = false ]; then
    print_header "Initial Cleanup"
    print_step "Cleaning up resources from previous runs"

    CLEANUP_FAILED=false
    for suite_spec in "${SUITES[@]}"; do
        # Parse suite specification to get directory
        suite_dir=""
        if [[ "$suite_spec" == *":"* ]]; then
            suite_dir="${suite_spec%%:*}"
        else
            suite_dir="$suite_spec"
        fi
        log_name="${suite_spec//:/_}"

        if [ -d "$suite_dir" ] && [ -f "$suite_dir/pipeline.yaml" ]; then
            echo "  Cleaning up $suite_spec..."
            
            # Create suite-specific output directory
            # Strip 'suites/' prefix to avoid duplication
            clean_log_name="${log_name#suites/}"
            suite_output_dir="$OUTPUT_DIR/suites/$clean_log_name"
            mkdir -p "$suite_output_dir"
            
            if [ "$SHOW_OUTPUT" = true ]; then
                # Show output in real-time while also capturing to log
                if FORCE_COLOR=1 python scripts/cleanup.py "$suite_spec" --yes $VERBOSE 2>&1 | tee "$suite_output_dir/initial_cleanup.log"; then
                    echo "    ✓ Cleaned"
                else
                    echo "    ⚠ Cleanup had issues (see $suite_output_dir/initial_cleanup.log)"
                    CLEANUP_FAILED=true
                fi
            else
                if python scripts/cleanup.py "$suite_spec" --yes $VERBOSE > "$suite_output_dir/initial_cleanup.log" 2>&1; then
                    echo "    ✓ Cleaned"
                else
                    echo "    ⚠ Cleanup had issues (see $suite_output_dir/initial_cleanup.log)"
                    CLEANUP_FAILED=true
                fi
            fi
        fi
    done

    if [ "$CLEANUP_FAILED" = false ]; then
        print_success "Initial cleanup completed"
    else
        print_error "Initial cleanup had some issues but continuing..."
    fi
    echo ""
else
    echo "Skipping initial cleanup"
    echo ""
fi

# Run each suite
for suite_spec in "${SUITES[@]}"; do
    # Choose execution function based on mode
    if [ "$LOCAL_MODE" = true ]; then
        run_func="run_suite_local"
    else
        run_func="run_suite"
    fi

    if $run_func "$suite_spec"; then
        if [ "${SUITE_RESULTS[$suite_spec]}" = "PASSED" ]; then
            print_success "✓ $suite_spec: ALL TESTS PASSED"
        else
            print_error "✗ $suite_spec: SOME TESTS FAILED"
            if [ "$STOP_ON_FAILURE" = true ]; then
                print_error "Stopping execution due to --stop-on-failure"
                break
            fi
        fi
    else
        print_error "✗ $suite_spec: SUITE FAILED"
        if [ "$STOP_ON_FAILURE" = true ]; then
            print_error "Stopping execution due to --stop-on-failure"
            break
        fi
    fi
    echo ""
done

TOTAL_END=$(date +%s)
TOTAL_DURATION=$((TOTAL_END - TOTAL_START))

# Print detailed failure information
HAS_FAILURES=false
for suite_spec in "${SUITES[@]}"; do
    suite_output_name="${suite_spec//:/_}"
    results_file="$OUTPUT_DIR/$suite_output_name/results.json"
    if [ -f "$results_file" ]; then
        # Check if there are failed tests
        failed_count=$(python -c "import json; d=json.load(open('$results_file')); print(d.get('failed', 0))" 2>/dev/null || echo "0")
        if [ "$failed_count" -gt 0 ]; then
            HAS_FAILURES=true
        fi
    fi
done

if [ "$HAS_FAILURES" = true ]; then
    print_header "Failed Tests Details"

    for suite_spec in "${SUITES[@]}"; do
        suite_output_name="${suite_spec//:/_}"
        results_file="$OUTPUT_DIR/$suite_output_name/results.json"
        if [ -f "$results_file" ]; then
            # Extract and display failed tests
            python - <<EOF
import json
import sys

try:
    with open('$results_file') as f:
        data = json.load(f)

    failed_tests = [r for r in data.get('results', []) if r.get('test_passed') == False]

    if failed_tests:
        print(f"\n${YELLOW}Suite: $suite_spec${NC}")
        print("─" * 70)

        for test in failed_tests:
            print(f"\n  ${RED}✗${NC} {test.get('pipeline_name', 'Unknown')}")

            # Show error if present
            error = test.get('error')
            output_error = test.get('output', {}).get('result', {}).get('error') if test.get('output') else None
            if error:
                print(f"    Error: {error[:200]}...")
            elif output_error:
                print(f"    Error: {output_error}")

            # Show RCA summary if present
            rca_summary = test.get('rca_summary')
            if rca_summary:
                print(f"\n    ${BLUE}RCA Analysis:${NC}")
                print(f"    {rca_summary[:150]}...")

                rca = test.get('rca', {})
                if rca:
                    print(f"\n    ${BLUE}Category:${NC} {rca.get('category', 'unknown')}")
                    print(f"    ${BLUE}Severity:${NC} {rca.get('severity', 'unknown')}")
                    print(f"    ${BLUE}Confidence:${NC} {rca.get('confidence', 'unknown')}")

                    fixes = rca.get('suggested_fix', [])
                    if fixes:
                        print(f"\n    ${BLUE}Suggested Fixes:${NC}")
                        for i, fix in enumerate(fixes[:3], 1):
                            print(f"      {i}. {fix[:80]}...")

                    refs = rca.get('code_references', [])
                    if refs:
                        print(f"\n    ${BLUE}Code References:${NC}")
                        for ref in refs[:3]:
                            print(f"      - {ref}")

            print()

except Exception as e:
    print(f"Error parsing results: {e}", file=sys.stderr)
EOF
        fi
    done
    echo ""
fi

# Print summary
print_header "Execution Summary"

echo "Suite Results:"
echo ""
printf "%-20s %-15s %-8s %-8s %-8s %-8s %-10s\n" "SUITE" "STATUS" "PASSED" "FAILED" "ERRORS" "SKIPPED" "DURATION"
echo "─────────────────────────────────────────────────────────────────────────────────────"

for suite_spec in "${SUITES[@]}"; do
    status="${SUITE_RESULTS[$suite_spec]:-NOT_RUN}"
    passed="${SUITE_PASSED[$suite_spec]:-0}"
    failed="${SUITE_FAILED[$suite_spec]:-0}"
    errors="${SUITE_ERRORS[$suite_spec]:-0}"
    skipped="${SUITE_SKIPPED[$suite_spec]:-0}"
    duration="${SUITE_DURATION[$suite_spec]:-0}"

    # Color code status
    case $status in
        PASSED)
            status_colored="${GREEN}PASSED${NC}"
            ;;
        TESTS_FAILED)
            status_colored="${YELLOW}TESTS_FAILED${NC}"
            ;;
        *)
            status_colored="${RED}${status}${NC}"
            ;;
    esac

    # Format suite column (truncate if too long)
    display_name="${suite_spec:0:20}"
    printf -v suite_col "%-20s" "$display_name"

    # Calculate padding for status to align with 15 char column
    status_len=${#status}
    if [ "$status_len" -lt 15 ]; then
        status_padding=$((15 - status_len))
        status_spaces=$(printf "%${status_padding}s" "")
    else
        status_spaces=""
    fi

    # Format other columns
    printf -v passed_col "%-8s" "$passed"
    printf -v failed_col "%-8s" "$failed"
    printf -v errors_col "%-8s" "$errors"
    printf -v skipped_col "%-8s" "$skipped"
    printf -v duration_col "%-10s" "${duration}s"

    # Print with color interpretation
    echo -e "${suite_col} ${status_colored}${status_spaces} ${passed_col} ${failed_col} ${errors_col} ${skipped_col} ${duration_col}"
done

echo ""
echo "Total execution time: ${TOTAL_DURATION}s"
echo ""
echo "Results saved to:"
for suite_spec in "${SUITES[@]}"; do
    suite_output_name="${suite_spec//:/_}"
    suite_output_name="${suite_output_name#suites/}"
    echo "  - $OUTPUT_DIR/suites/$suite_output_name/"
done
echo ""

# Calculate overall success
OVERALL_SUCCESS=true
for suite_spec in "${SUITES[@]}"; do
    status="${SUITE_RESULTS[$suite_spec]:-NOT_RUN}"
    if [ "$status" != "PASSED" ]; then
        OVERALL_SUCCESS=false
        break
    fi
done

if [ "$OVERALL_SUCCESS" = true ]; then
    print_success "All suites passed!"
    exit 0
else
    print_error "Some suites failed or had errors"
    exit 1
fi
