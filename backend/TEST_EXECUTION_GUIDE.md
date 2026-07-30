# Test Execution Guide - Payment System
## Quick Start & Command Reference

---

## 1. Setup

### Install Dependencies
```bash
cd backend
pip install -r requirements.txt
pip install -r requirements-test.txt  # If separate test requirements exist
```

### Alternative Installation
```bash
pip install pytest pytest-asyncio pytest-cov pytest-mock httpx sqlalchemy pydantic
```

---

## 2. Running Tests

### Quick Start - Run All Tests
```bash
# Run all tests with verbose output
pytest -v

# Run all tests with minimal output
pytest

# Run tests from specific directory
pytest tests/ -v
```

### Run Specific Test Categories

#### Unit Tests Only
```bash
pytest tests/test_payment_service.py -v
```

#### Integration Tests Only
```bash
pytest tests/test_payment_endpoints.py -v
```

#### End-to-End Tests Only
```bash
pytest tests/test_e2e_booking_payment.py -v
```

#### Security Tests Only
```bash
pytest tests/test_payment_security.py -v
```

### Run Specific Test Classes
```bash
# Test payment creation only
pytest tests/test_payment_service.py::TestCreatePayment -v

# Test signature verification only
pytest tests/test_payment_service.py::TestSignatureVerification -v

# Test webhook handling only
pytest tests/test_payment_service.py::TestWebhookHandling -v
```

### Run Specific Individual Tests
```bash
# Run single test
pytest tests/test_payment_service.py::TestCreatePayment::test_create_payment_success -v

# Run multiple specific tests
pytest tests/test_payment_service.py::TestCreatePayment::test_create_payment_success \
       tests/test_payment_service.py::TestCreatePayment::test_create_payment_invalid_booking -v
```

---

## 3. Coverage Reports

### Generate Coverage Report
```bash
# Basic coverage
pytest --cov=services/payment_service tests/

# HTML coverage report
pytest --cov=services/payment_service --cov-report=html tests/
# Open htmlcov/index.html in browser

# Terminal coverage report with line numbers
pytest --cov=services/payment_service --cov-report=term-missing tests/

# All report formats
pytest --cov=services/payment_service \
       --cov-report=html \
       --cov-report=xml \
       --cov-report=term-missing tests/
```

### Coverage Threshold Validation
```bash
# Fail if coverage < 95%
pytest --cov=services/payment_service --cov-fail-under=95 tests/

# Fail if coverage < 90%
pytest --cov=services/payment_service --cov-fail-under=90 tests/
```

### Coverage for Specific Files
```bash
# Coverage for just payment_service.py
pytest --cov=services/payment_service tests/test_payment_service.py

# Coverage for payment endpoints
pytest --cov=api/payments tests/test_payment_endpoints.py
```

---

## 4. Test Markers & Filtering

### Using Pytest Markers
```bash
# Run only security tests
pytest -m security -v

# Run only integration tests
pytest -m integration -v

# Run only asyncio tests
pytest -m asyncio -v

# Run payment-specific tests
pytest -m payment -v

# Run webhook tests
pytest -m webhook -v

# Exclude security tests
pytest -m "not security" -v

# Run unit OR integration tests
pytest -m "unit or integration" -v
```

---

## 5. Advanced Execution Options

### Parallel Test Execution
```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel (4 workers)
pytest -n 4 -v

# Run with auto-detected number of CPUs
pytest -n auto -v
```

### Failed Test Re-run
```bash
# Run only failed tests from last run
pytest --lf -v

# Run failed tests first, then others
pytest --ff -v
```

### Stop on First Failure
```bash
# Stop after first failure
pytest -x

# Stop after 3 failures
pytest --maxfail=3
```

### Verbose Output Options
```bash
# Very verbose (show all assert details)
pytest -vv

# Show print statements
pytest -s

# Show local variables on failure
pytest -l
```

### Keyword-based Selection
```bash
# Run tests matching keyword
pytest -k "payment_creation" -v

# Run tests NOT matching keyword
pytest -k "not webhook" -v

# Run tests matching multiple keywords
pytest -k "payment and success" -v
```

---

## 6. Output & Reporting

### Save Test Results
```bash
# Save results to JUnit XML
pytest --junit-xml=test_results.xml tests/

# Save results to HTML
pytest --html=report.html --self-contained-html tests/

# Save to JSON (requires pytest-json-report)
pip install pytest-json-report
pytest --json-report --json-report-file=report.json tests/
```

### Custom Output Format
```bash
# Minimal output
pytest --tb=no -q

# Short traceback
pytest --tb=short

# Line traceback
pytest --tb=line

# Native Python traceback
pytest --tb=native

# Full traceback (default)
pytest --tb=long
```

---

## 7. Performance & Timing

### Show Test Duration
```bash
# Show slowest 10 tests
pytest --durations=10

# Show all test durations
pytest --durations=0

# Show tests taking longer than 1s
pytest --durations=1 -v
```

### Timeout Configuration
```bash
# Install pytest-timeout
pip install pytest-timeout

# Set 30-second timeout for all tests
pytest --timeout=30

# Set per-test timeout (uses marker)
# @pytest.mark.timeout(60)
```

---

## 8. Interactive Mode

### Debug Individual Tests
```bash
# Enter debugger on failure
pytest --pdb -x

# Enter debugger before test
pytest --trace

# Drop to shell on failure
pytest --pdbcls=IPython.terminal.debugger:TerminalPdb
```

### Ask Before Running Tests
```bash
# Prompt for test selection
pytest --collect-only  # List tests without running
```

---

## 9. Test Environment Configuration

### Use Different Configuration
```bash
# Set environment variables
export RAZORPAY_KEY_ID=test_key
export RAZORPAY_KEY_SECRET=test_secret
export DATABASE_URL=sqlite:///:memory:

pytest tests/
```

### Using .env File
```bash
# Create .env.test
RAZORPAY_KEY_ID=test_key
RAZORPAY_KEY_SECRET=test_secret

# Load and run
python -m dotenv -f .env.test load
pytest tests/
```

---

## 10. Continuous Integration

### GitHub Actions
```yaml
name: Payment Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt pytest pytest-cov
      - run: pytest --cov=services/payment_service --cov-fail-under=95 tests/
```

### GitLab CI
```yaml
test:
  image: python:3.10
  script:
    - pip install -r requirements.txt pytest pytest-cov
    - pytest --cov=services/payment_service tests/
  coverage: '/TOTAL.*\s+(\d+%)$/'
```

---

## 11. Common Issues & Solutions

### Issue: Import Errors
```bash
# Solution 1: Add to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"
pytest

# Solution 2: Run from backend directory
cd backend
pytest

# Solution 3: Use pytest plugin
pip install pytest-pythonpath
```

### Issue: Async Tests Fail
```bash
# Solution: Ensure pytest-asyncio is installed and configured
pip install pytest-asyncio

# Add to pytest.ini:
# asyncio_mode = auto
```

### Issue: Database Locked
```bash
# Solution 1: Use in-memory SQLite
# Tests should use sqlite:///:memory:

# Solution 2: Run tests sequentially
pytest -n 1

# Solution 3: Clear temp files
rm -rf .pytest_cache
```

### Issue: Tests Hang/Timeout
```bash
# Run with timeout
pytest --timeout=30

# Run with verbose to see where it hangs
pytest -vvs

# Check for infinite loops or deadlocks
```

### Issue: Fixtures Not Working
```bash
# Verify conftest.py is in same directory
ls tests/conftest.py

# Check fixture names are spelled correctly
pytest --fixtures  # List all available fixtures

# Use -vv to see fixture usage
pytest -vv
```

---

## 12. Quick Commands Reference

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=services/payment_service --cov-report=html

# Run specific file
pytest tests/test_payment_service.py

# Run specific class
pytest tests/test_payment_service.py::TestCreatePayment

# Run specific test
pytest tests/test_payment_service.py::TestCreatePayment::test_create_payment_success

# Run with markers
pytest -m security

# Run failed tests
pytest --lf

# Show slowest tests
pytest --durations=10

# Stop on first failure
pytest -x

# Verbose output
pytest -vv

# Show print statements
pytest -s

# Save coverage HTML
pytest --cov=services/payment_service --cov-report=html && open htmlcov/index.html

# Parallel execution
pytest -n auto

# Check test collection
pytest --collect-only
```

---

## 13. Pre-Commit Hook Setup

### Setup Auto-Test on Commit
```bash
# Create .git/hooks/pre-commit
#!/bin/bash
pytest --cov=services/payment_service --cov-fail-under=95 || exit 1

# Make executable
chmod +x .git/hooks/pre-commit
```

---

## 14. Performance Expectations

| Operation | Expected Time |
|-----------|---------------|
| Unit tests only | 5-10 seconds |
| All tests | 30-60 seconds |
| With coverage | 45-90 seconds |
| Full suite + HTML report | 60-120 seconds |

---

## 15. Test Data Cleanup

### Clear Test Database
```bash
# SQLite auto-cleanup (in-memory)
# No action needed - deleted after test

# If using persistent SQLite:
rm -f test.db

# If using PostgreSQL:
DROP DATABASE test_db;
```

---

## Final Checklist Before Deployment

- [ ] All tests pass: `pytest`
- [ ] Coverage ≥95%: `pytest --cov-fail-under=95`
- [ ] No security warnings: `pytest -m security`
- [ ] Performance acceptable: `pytest --durations=10`
- [ ] HTML report generated: `htmlcov/index.html`
- [ ] CI pipeline passes
- [ ] No warnings or errors in logs

---

**Created**: June 8, 2026  
**Team**: Team 5 - QA & Testing  
**Status**: Complete & Ready for Use
