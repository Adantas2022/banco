#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

show_help() {
    echo "IRPF Processor Test Runner"
    echo ""
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  unit          Run unit tests only (no dependencies)"
    echo "  integration   Run integration tests (requires docker services)"
    echo "  e2e           Run end-to-end tests"
    echo "  all           Run all tests with coverage"
    echo "  docker        Run all tests in docker containers"
    echo "  coverage      Generate coverage report"
    echo "  lint          Run linter (ruff)"
    echo "  typecheck     Run type checker (mypy)"
    echo "  clean         Clean up test artifacts"
    echo ""
    echo "Options:"
    echo "  -v, --verbose     Verbose output"
    echo "  -k EXPRESSION     Run tests matching expression"
    echo "  -x, --exitfirst   Exit on first failure"
    echo "  --no-cov          Disable coverage"
    echo "  -h, --help        Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 unit                    # Run unit tests"
    echo "  $0 unit -k 'test_parser'   # Run unit tests matching 'test_parser'"
    echo "  $0 docker                  # Run all tests in Docker"
    echo "  $0 coverage                # Generate HTML coverage report"
}

VERBOSE=""
EXPRESSION=""
EXITFIRST=""
NO_COV=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE="-v"
            shift
            ;;
        -k)
            EXPRESSION="-k $2"
            shift 2
            ;;
        -x|--exitfirst)
            EXITFIRST="-x"
            shift
            ;;
        --no-cov)
            NO_COV="true"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            COMMAND=$1
            shift
            ;;
    esac
done

COMMAND=${COMMAND:-"unit"}

run_unit_tests() {
    log_info "Running unit tests..."
    
    PYTEST_ARGS="tests/unit/ $VERBOSE $EXPRESSION $EXITFIRST"
    
    if [ -z "$NO_COV" ]; then
        PYTEST_ARGS="$PYTEST_ARGS --cov=irpf_processor --cov-report=term-missing"
    fi
    
    python -m pytest $PYTEST_ARGS
    
    log_success "Unit tests completed"
}

run_integration_tests() {
    log_info "Running integration tests..."
    
    PYTEST_ARGS="tests/integration/ $VERBOSE $EXPRESSION $EXITFIRST -m integration"
    
    python -m pytest $PYTEST_ARGS
    
    log_success "Integration tests completed"
}

run_e2e_tests() {
    log_info "Running end-to-end tests..."
    
    PYTEST_ARGS="tests/e2e/ $VERBOSE $EXPRESSION $EXITFIRST -m e2e"
    
    python -m pytest $PYTEST_ARGS
    
    log_success "E2E tests completed"
}

run_all_tests() {
    log_info "Running all tests..."
    
    PYTEST_ARGS="tests/ $VERBOSE $EXPRESSION $EXITFIRST"
    
    if [ -z "$NO_COV" ]; then
        PYTEST_ARGS="$PYTEST_ARGS --cov=irpf_processor --cov-report=term-missing --cov-report=html:coverage_html"
    fi
    
    python -m pytest $PYTEST_ARGS
    
    log_success "All tests completed"
}

run_docker_tests() {
    log_info "Running tests in Docker..."
    
    docker compose -f docker-compose.test.yml down -v 2>/dev/null || true
    
    docker compose -f docker-compose.test.yml build test-runner
    
    docker compose -f docker-compose.test.yml run --rm test-runner
    EXIT_CODE=$?
    
    docker compose -f docker-compose.test.yml down -v
    
    if [ $EXIT_CODE -eq 0 ]; then
        log_success "Docker tests completed successfully"
    else
        log_error "Docker tests failed with exit code $EXIT_CODE"
        exit $EXIT_CODE
    fi
}

run_docker_unit_tests() {
    log_info "Running unit tests in Docker..."
    
    docker compose -f docker-compose.test.yml build test-unit
    docker compose -f docker-compose.test.yml run --rm test-unit
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        log_success "Docker unit tests completed successfully"
    else
        log_error "Docker unit tests failed with exit code $EXIT_CODE"
        exit $EXIT_CODE
    fi
}

run_docker_integration_tests() {
    log_info "Running integration tests in Docker..."
    
    docker compose -f docker-compose.test.yml down -v 2>/dev/null || true
    
    docker compose -f docker-compose.test.yml build test-integration
    docker compose -f docker-compose.test.yml run --rm test-integration
    EXIT_CODE=$?
    
    docker compose -f docker-compose.test.yml down -v
    
    if [ $EXIT_CODE -eq 0 ]; then
        log_success "Docker integration tests completed successfully"
    else
        log_error "Docker integration tests failed with exit code $EXIT_CODE"
        exit $EXIT_CODE
    fi
}

generate_coverage() {
    log_info "Generating coverage report..."
    
    python -m pytest tests/ \
        --cov=irpf_processor \
        --cov-report=html:coverage_html \
        --cov-report=xml:coverage.xml \
        --cov-report=term-missing \
        $VERBOSE
    
    log_success "Coverage report generated at coverage_html/index.html"
}

run_lint() {
    log_info "Running linter (ruff)..."
    
    ruff check src/ tests/
    ruff format --check src/ tests/
    
    log_success "Linting completed"
}

run_typecheck() {
    log_info "Running type checker (mypy)..."
    
    mypy src/irpf_processor
    
    log_success "Type checking completed"
}

clean_artifacts() {
    log_info "Cleaning test artifacts..."
    
    rm -rf .pytest_cache
    rm -rf coverage_html
    rm -rf .coverage
    rm -f coverage.xml
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    
    docker compose -f docker-compose.test.yml down -v 2>/dev/null || true
    
    log_success "Cleanup completed"
}

case $COMMAND in
    unit)
        run_unit_tests
        ;;
    integration)
        run_integration_tests
        ;;
    e2e)
        run_e2e_tests
        ;;
    all)
        run_all_tests
        ;;
    docker)
        run_docker_tests
        ;;
    docker-unit)
        run_docker_unit_tests
        ;;
    docker-integration)
        run_docker_integration_tests
        ;;
    coverage)
        generate_coverage
        ;;
    lint)
        run_lint
        ;;
    typecheck)
        run_typecheck
        ;;
    clean)
        clean_artifacts
        ;;
    *)
        log_error "Unknown command: $COMMAND"
        show_help
        exit 1
        ;;
esac
