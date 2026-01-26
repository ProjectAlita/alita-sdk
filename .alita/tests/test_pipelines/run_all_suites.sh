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
OUTPUT_DIR="test_results"

print_usage() {
    echo "Usage: $0 [OPTIONS] [SUITE...]"
    echo ""
    echo "Run test suites with full workflow (setup, seed, run, cleanup)"
    echo ""
    echo "Options:"
    echo "  -v, --verbose           Enable verbose output"
    echo "  --show-output           Show verbose test execution in real-time (implies -v)"
    echo "  --local                 Run tests locally without backend (isolated mode)"
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
    echo "  $0 --show-output github_toolkit # Show live test execution"
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
            shift
            ;;
        --show-output)
            VERBOSE="--verbose"
            SHOW_OUTPUT=true
            shift
            ;;
        --local)
            LOCAL_MODE=true
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

# Summary tracking
declare -A SUITE_RESULTS
declare -A SUITE_PASSED
declare -A SUITE_FAILED
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
        SUITE_RESULTS[$suite_spec]="FAILED"
        return 1
    fi

    # Check if pipeline config exists
    local config_file="${pipeline_file:-pipeline.yaml}"
    if [ ! -f "$suite_dir/$config_file" ]; then
        print_error "$config_file not found in $suite_dir/"
        SUITE_RESULTS[$suite_spec]="FAILED"
        return 1
    fi

    # Create output directory using sanitized suite name (replace : with _)
    local suite_output_name="${suite_spec//:/_}"
    local suite_output_dir="$OUTPUT_DIR/$suite_output_name"
    mkdir -p "$suite_output_dir"

    # Step 1: Setup
    if [ "$SKIP_SETUP" = false ]; then
        print_step "Step 1/4: Running setup for $suite_spec"
        if python scripts/setup.py "$suite_spec" $VERBOSE --output-env .env > "$suite_output_dir/setup.log" 2>&1; then
            print_success "Setup completed"
        else
            print_error "Setup failed - see $suite_output_dir/setup.log"
            SUITE_RESULTS[$suite_spec]="SETUP_FAILED"
            cat "$suite_output_dir/setup.log"
            return 1
        fi
    else
        echo "  Skipping setup (using existing environment)"
    fi

    # Step 2: Seed pipelines
    print_step "Step 2/4: Seeding pipelines for $suite_spec"
    if python scripts/seed_pipelines.py "$suite_spec" --env-file .env $VERBOSE > "$suite_output_dir/seed.log" 2>&1; then
        print_success "Pipelines seeded"
    else
        print_error "Seeding failed - see $suite_output_dir/seed.log"
        SUITE_RESULTS[$suite_spec]="SEED_FAILED"
        cat "$suite_output_dir/seed.log"
        return 1
    fi

    # Step 3: Run tests
    print_step "Step 3/4: Running tests for $suite_spec"
    local results_file="$suite_output_dir/results.json"

    # Run tests with JSON output to stdout (results_file) and verbose to stderr (run.log)
    # Now verbose output goes to stderr, so we can use both --json and $VERBOSE together
    if [ "$SHOW_OUTPUT" = true ]; then
        # Show verbose output in real-time while also capturing to log
        if python scripts/run_suite.py "$suite_spec" --json $VERBOSE > "$results_file" 2> >(tee "$suite_output_dir/run.log" >&2); then
            print_success "Tests completed"
        else
            print_error "Test execution failed - see $suite_output_dir/run.log"
            SUITE_RESULTS[$suite_spec]="RUN_FAILED"
            cat "$suite_output_dir/run.log"
            return 1
        fi
    else
        # Capture verbose output to log file only
        if python scripts/run_suite.py "$suite_spec" --json $VERBOSE > "$results_file" 2> "$suite_output_dir/run.log"; then
            print_success "Tests completed"
        else
            print_error "Test execution failed - see $suite_output_dir/run.log"
            SUITE_RESULTS[$suite_spec]="RUN_FAILED"
            cat "$suite_output_dir/run.log"
            return 1
        fi
    fi

    # Parse results
    if [ -f "$results_file" ]; then
        local passed=$(python -c "import json; data=json.load(open('$results_file')); print(data.get('passed', 0))" 2>/dev/null || echo "0")
        local failed=$(python -c "import json; data=json.load(open('$results_file')); print(data.get('failed', 0))" 2>/dev/null || echo "0")
        local total=$(python -c "import json; data=json.load(open('$results_file')); print(data.get('total', 0))" 2>/dev/null || echo "0")

        SUITE_PASSED[$suite_spec]=$passed
        SUITE_FAILED[$suite_spec]=$failed

        echo "  Results: $passed passed, $failed failed (total: $total)"

        if [ "$failed" -gt 0 ]; then
            SUITE_RESULTS[$suite_spec]="TESTS_FAILED"
            print_error "Some tests failed"
        else
            SUITE_RESULTS[$suite_spec]="PASSED"
        fi
    else
        print_error "Test execution failed - see $suite_output_dir/run.log"
        SUITE_RESULTS[$suite_spec]="RUN_FAILED"
        cat "$suite_output_dir/run.log"
        return 1
    fi

    # Step 4: Cleanup
    if [ "$SKIP_CLEANUP" = false ]; then
        print_step "Step 4/4: Cleaning up $suite_spec"
        if python scripts/cleanup.py "$suite_spec" --yes $VERBOSE > "$suite_output_dir/cleanup.log" 2>&1; then
            print_success "Cleanup completed"
        else
            print_error "Cleanup failed - see $suite_output_dir/cleanup.log (continuing anyway)"
            # Don't fail suite on cleanup failure
        fi
    else
        echo "  Skipping cleanup"
    fi

    local suite_end=$(date +%s)
    local suite_duration=$((suite_end - suite_start))
    SUITE_DURATION[$suite_spec]=$suite_duration

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
        SUITE_RESULTS[$suite_spec]="FAILED"
        return 1
    fi

    # Check if pipeline config exists
    local config_file="${pipeline_file:-pipeline.yaml}"
    if [ ! -f "$suite_dir/$config_file" ]; then
        print_error "$config_file not found in $suite_dir/"
        SUITE_RESULTS[$suite_spec]="FAILED"
        return 1
    fi

    # Create output directory using sanitized suite name (replace : with _)
    local suite_output_name="${suite_spec//:/_}"
    local suite_output_dir="$OUTPUT_DIR/$suite_output_name"
    mkdir -p "$suite_output_dir"

    # Step 1: Setup (with --local flag)
    print_step "Step 1/: Running setup for $suite_spec (local)"
    if python scripts/setup.py "$suite_spec" $VERBOSE --output-env .env --local > "$suite_output_dir/setup.log" 2>&1; then
        print_success "Setup completed"
    else
        print_error "Setup failed - see $suite_output_dir/setup.log"
        SUITE_RESULTS[$suite_spec]="SETUP_FAILED"
        cat "$suite_output_dir/setup.log"
        return 1
    fi

    # Step 3: Run tests (with --local flag)
    print_step "Step 2/3: Running tests for $suite_spec (local)"
    local results_file="$suite_output_dir/results.json"

    if python scripts/run_suite.py "$suite_spec" --json $VERBOSE --local > "$results_file" 2> "$suite_output_dir/run.log"; then
        print_success "Tests completed"

        # Parse results
        if [ -f "$results_file" ]; then
            local passed=$(python -c "import json; data=json.load(open('$results_file')); print(data.get('passed', 0))" 2>/dev/null || echo "0")
            local failed=$(python -c "import json; data=json.load(open('$results_file')); print(data.get('failed', 0))" 2>/dev/null || echo "0")
            local total=$(python -c "import json; data=json.load(open('$results_file')); print(data.get('total_tests', 0))" 2>/dev/null || echo "0")

            SUITE_PASSED[$suite_spec]=$passed
            SUITE_FAILED[$suite_spec]=$failed

            echo "  Results: $passed passed, $failed failed (total: $total)"

            if [ "$failed" -gt 0 ]; then
                SUITE_RESULTS[$suite_spec]="TESTS_FAILED"
                print_error "Some tests failed"
            else
                SUITE_RESULTS[$suite_spec]="PASSED"
            fi
        fi
    else
        print_error "Test execution failed - see $suite_output_dir/run.log"
        SUITE_RESULTS[$suite_spec]="RUN_FAILED"
        cat "$suite_output_dir/run.log"
        return 1
    fi

    # Step 3: Cleanup (with --local flag)
    if [ "$SKIP_CLEANUP" = false ]; then
        print_step "Step 3/3: Cleaning up $suite_spec (local)"
        if python scripts/cleanup.py "$suite_spec" --yes $VERBOSE --local > "$suite_output_dir/cleanup.log" 2>&1; then
            print_success "Cleanup completed"
        else
            print_error "Cleanup failed - see $suite_output_dir/cleanup.log (continuing anyway)"
            # Don't fail suite on cleanup failure
        fi
    else
        echo "  Skipping cleanup"
    fi

    local suite_end=$(date +%s)
    local suite_duration=$((suite_end - suite_start))
    SUITE_DURATION[$suite_spec]=$suite_duration

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
            if python scripts/cleanup.py "$suite_spec" --yes $VERBOSE > "$OUTPUT_DIR/${log_name}_initial_cleanup.log" 2>&1; then
                echo "    ✓ Cleaned"
            else
                echo "    ⚠ Cleanup had issues (see $OUTPUT_DIR/${log_name}_initial_cleanup.log)"
                CLEANUP_FAILED=true
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
printf "%-20s %-15s %-10s %-10s %-10s\n" "SUITE" "STATUS" "PASSED" "FAILED" "DURATION"
echo "─────────────────────────────────────────────────────────────────────"

for suite_spec in "${SUITES[@]}"; do
    status="${SUITE_RESULTS[$suite_spec]:-NOT_RUN}"
    passed="${SUITE_PASSED[$suite_spec]:-0}"
    failed="${SUITE_FAILED[$suite_spec]:-0}"
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
    status_padding=$((15 - status_len))
    status_spaces=$(printf "%${status_padding}s" "")

    # Format other columns
    printf -v passed_col "%-10s" "$passed"
    printf -v failed_col "%-10s" "$failed"
    printf -v duration_col "%-10s" "${duration}s"

    # Print with color interpretation
    echo -e "${suite_col} ${status_colored}${status_spaces} ${passed_col} ${failed_col} ${duration_col}"
done

echo ""
echo "Total execution time: ${TOTAL_DURATION}s"
echo "Results saved to: $OUTPUT_DIR/"
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
