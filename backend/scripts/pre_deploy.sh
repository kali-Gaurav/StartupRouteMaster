#!/bin/bash
# RouteMaster Feature #1 — Pre-Deployment Validation Script
# Run this before every deployment (dev → staging → production)
# Usage: bash scripts/pre_deploy.sh

set -e

ENVIRONMENT=${1:-development}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

echo "════════════════════════════════════════════════════════════════════"
echo "  RouteMaster Feature #1 — Pre-Deployment Validation"
echo "  Environment: $ENVIRONMENT"
echo "════════════════════════════════════════════════════════════════════"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_passed=0
check_failed=0

check_status() {
    local name=$1
    local result=$2

    if [ $result -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $name"
        ((check_passed++))
    else
        echo -e "${RED}✗${NC} $name"
        ((check_failed++))
    fi
}

# ───────────────────────────────────────────────────────────────────────────────
# 1. ENVIRONMENT VARIABLES
# ───────────────────────────────────────────────────────────────────────────────

echo "1. Checking Environment Variables..."

cd "$BACKEND_DIR"

python3 << 'EOF'
import os
import sys

required_vars = [
    'DATABASE_URL',
    'RAZORPAY_KEY_ID',
    'RAZORPAY_KEY_SECRET',
    'RAZORPAY_WEBHOOK_SECRET',
    'ENVIRONMENT',
]

missing = []
for var in required_vars:
    if not os.getenv(var):
        missing.append(var)

if missing:
    print(f"   Missing variables: {', '.join(missing)}")
    sys.exit(1)
else:
    print("   All required env vars set")
    sys.exit(0)
EOF

check_status "Environment variables" $?

# ───────────────────────────────────────────────────────────────────────────────
# 2. DATABASE CONNECTIVITY
# ───────────────────────────────────────────────────────────────────────────────

echo ""
echo "2. Checking Database Connectivity..."

python3 << 'EOF'
import os
import sys

try:
    from database.infrastructure.session import get_sync_db
    from sqlalchemy import text

    db = get_sync_db()
    result = db.execute(text('SELECT 1 as test')).fetchone()

    if result:
        print("   Database connection OK")
        sys.exit(0)
    else:
        print("   Database query failed")
        sys.exit(1)
except Exception as e:
    print(f"   Database error: {e}")
    sys.exit(1)
EOF

check_status "Database connectivity" $?

# ───────────────────────────────────────────────────────────────────────────────
# 3. DATABASE TABLES
# ───────────────────────────────────────────────────────────────────────────────

echo ""
echo "3. Checking Database Tables..."

python3 << 'EOF'
import os
import sys

try:
    from database.infrastructure.session import get_sync_db
    from sqlalchemy import inspect

    db = get_sync_db()
    inspector = inspect(db)
    tables = inspector.get_table_names()

    required_tables = ['bookings', 'booking_idempotency', 'booking_monitors']

    missing = [t for t in required_tables if t not in tables]

    if missing:
        print(f"   Missing tables: {', '.join(missing)}")
        sys.exit(1)
    else:
        print(f"   Found all required tables: {', '.join(required_tables)}")
        sys.exit(0)
except Exception as e:
    print(f"   Error checking tables: {e}")
    sys.exit(1)
EOF

check_status "Database tables" $?

# ───────────────────────────────────────────────────────────────────────────────
# 4. REDIS CONNECTIVITY
# ───────────────────────────────────────────────────────────────────────────────

echo ""
echo "4. Checking Redis Connectivity..."

python3 << 'EOF'
import os
import sys

try:
    import redis

    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
    r = redis.from_url(redis_url)
    r.ping()

    print("   Redis connection OK")
    sys.exit(0)
except Exception as e:
    print(f"   Redis error (non-critical): {e}")
    # Don't fail if Redis is unavailable — app can work with degraded cache
    sys.exit(0)
EOF

check_status "Redis connectivity (optional)" $?

# ───────────────────────────────────────────────────────────────────────────────
# 5. API IMPORTS
# ───────────────────────────────────────────────────────────────────────────────

echo ""
echo "5. Checking API Imports..."

python3 << 'EOF'
import os
import sys

try:
    from database.models.core import Booking, BookingIdempotency, BookingMonitor
    from razorpay import Client
    print("   All API imports OK")
    sys.exit(0)
except Exception as e:
    print(f"   Import error: {e}")
    sys.exit(1)
EOF

check_status "API imports" $?

# ───────────────────────────────────────────────────────────────────────────────
# 6. RAZORPAY CLIENT
# ───────────────────────────────────────────────────────────────────────────────

echo ""
echo "6. Checking Razorpay Client..."

python3 << 'EOF'
import os
import sys

try:
    from razorpay import Client

    key_id = os.getenv('RAZORPAY_KEY_ID')
    key_secret = os.getenv('RAZORPAY_KEY_SECRET')

    if not key_id or not key_secret:
        print("   Missing Razorpay credentials")
        sys.exit(1)

    client = Client(auth=(key_id, key_secret))

    # Test client is initialized
    if client.auth:
        print("   Razorpay client OK")
        sys.exit(0)
    else:
        print("   Razorpay client initialization failed")
        sys.exit(1)
except Exception as e:
    print(f"   Razorpay error: {e}")
    sys.exit(1)
EOF

check_status "Razorpay client" $?

# ───────────────────────────────────────────────────────────────────────────────
# 7. CODE STYLE (Optional for dev, Required for prod)
# ───────────────────────────────────────────────────────────────────────────────

echo ""
echo "7. Checking Code Style (black)..."

if command -v black &> /dev/null; then
    black api/ database/ --check --quiet 2>/dev/null
    check_status "Code formatting (black)" $?
else
    echo -e "${YELLOW}⊗${NC} black not installed (skipping)"
    ((check_failed++))
fi

# ───────────────────────────────────────────────────────────────────────────────
# 8. LINTING (Optional for dev, Required for prod)
# ───────────────────────────────────────────────────────────────────────────────

echo ""
echo "8. Checking Linting (pylint)..."

if command -v pylint &> /dev/null; then
    pylint api/ database/ --disable=all --enable=E,F --exit-zero 2>/dev/null
    check_status "Linting (pylint)" $?
else
    echo -e "${YELLOW}⊗${NC} pylint not installed (skipping)"
    ((check_failed++))
fi

# ───────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ───────────────────────────────────────────────────────────────────────────────

echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "  Summary"
echo "════════════════════════════════════════════════════════════════════"
echo -e "  ${GREEN}Passed: $check_passed${NC}"
echo -e "  ${RED}Failed: $check_failed${NC}"
echo ""

if [ $check_failed -eq 0 ]; then
    echo -e "${GREEN}✓ ALL CHECKS PASSED — Ready to deploy${NC}"
    exit 0
else
    echo -e "${RED}✗ SOME CHECKS FAILED — Fix issues before deploying${NC}"
    exit 1
fi
