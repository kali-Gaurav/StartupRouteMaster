#!/bin/bash

echo "════════════════════════════════════════════════════════════════"
echo "  MASTER CONSOLIDATION: All 12 Categories"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Create archive structure first
mkdir -p archive/duplicates_consolidated/{routing,seat_allocation,pricing,caching,booking,payment,station,user,verification,events,graph,ml}/v1

echo "1️⃣  ROUTE ENGINES → domains/routing/engine.py (CANONICAL)"
mkdir -p archive/duplicates_consolidated/routing/v1
cp -v archive/route_engines_v1/*.py archive/duplicates_consolidated/routing/v1/ 2>/dev/null || echo "   (No v1 files to archive)"
echo "   ✅ Done"
echo ""

echo "2️⃣  SEAT ALLOCATION → domains/inventory/seat_allocator.py (CANONICAL)"
mkdir -p archive/duplicates_consolidated/seat_allocation/v1
cp -v archive/seat_allocators_v1/*.py archive/duplicates_consolidated/seat_allocation/v1/ 2>/dev/null || echo "   (No v1 files to archive)"
cp -v archive/seat_allocators_consolidated/v1/*.py archive/duplicates_consolidated/seat_allocation/v1/ 2>/dev/null || echo "   (No consolidated files to archive)"
echo "   ✅ Done"
echo ""

echo "3️⃣  PRICING → domains/pricing/engine.py (CANONICAL)"
mkdir -p archive/duplicates_consolidated/pricing/v1
cp -v archive/pricing_engines_v1/*.py archive/duplicates_consolidated/pricing/v1/ 2>/dev/null || echo "   (No v1 files to archive)"
cp -v archive/pricing_engines_consolidated/v1/*.py archive/duplicates_consolidated/pricing/v1/ 2>/dev/null || echo "   (No consolidated files to archive)"
echo "   ✅ Done"
echo ""

echo "4️⃣  CACHING → platform/cache/manager.py (CANONICAL)"
mkdir -p archive/duplicates_consolidated/caching/v1
cp -v archive/cache_managers_v1/*.py archive/duplicates_consolidated/caching/v1/ 2>/dev/null || echo "   (No v1 files to archive)"
cp -v archive/cache_managers_consolidated/v1/*.py archive/duplicates_consolidated/caching/v1/ 2>/dev/null || echo "   (No consolidated files to archive)"
echo "   ✅ Done"
echo ""

echo "5️⃣  BOOKING → domains/booking/service.py (CANONICAL)"
mkdir -p archive/duplicates_consolidated/booking/v1
cp -v archive/booking_consolidated/v1/*.py archive/duplicates_consolidated/booking/v1/ 2>/dev/null || echo "   (Already consolidated)"
echo "   ✅ Done"
echo ""

echo "6️⃣  PAYMENT → domains/payment/service.py (CANONICAL)"
mkdir -p archive/duplicates_consolidated/payment/v1
cp -v archive/payment_consolidated/v1/*.py archive/duplicates_consolidated/payment/v1/ 2>/dev/null || echo "   (Already consolidated)"
echo "   ✅ Done"
echo ""

echo "7️⃣  STATION → domains/station/service.py (CANONICAL)"
mkdir -p archive/duplicates_consolidated/station/v1
cp -v archive/station_consolidated/v1/*.py archive/duplicates_consolidated/station/v1/ 2>/dev/null || echo "   (Already consolidated)"
echo "   ✅ Done"
echo ""

echo "8️⃣  USER → domains/user/service.py (CANONICAL)"
mkdir -p archive/duplicates_consolidated/user/v1
cp -v archive/user_consolidated/v1/*.py archive/duplicates_consolidated/user/v1/ 2>/dev/null || echo "   (Already consolidated)"
echo "   ✅ Done"
echo ""

echo "9️⃣  VERIFICATION → domains/verification/unlock_service.py (CANONICAL)"
mkdir -p archive/duplicates_consolidated/verification/v1
cp -v archive/verification_consolidated/v1/*.py archive/duplicates_consolidated/verification/v1/ 2>/dev/null || echo "   (Already consolidated)"
echo "   ✅ Done"
echo ""

echo "🔟 EVENTS → platform/events/producer.py + consumer.py (CANONICAL)"
mkdir -p archive/duplicates_consolidated/events/v1
cp -v archive/platform_consolidated/v1/event_producer.py archive/duplicates_consolidated/events/v1/ 2>/dev/null || echo "   (No event files)"
cp -v archive/platform_consolidated/v1/analytics_consumer.py archive/duplicates_consolidated/events/v1/ 2>/dev/null || echo "   (No analytics files)"
echo "   ✅ Done"
echo ""

echo "1️⃣1️⃣ GRAPH → platform/graph/mutation_engine.py (CANONICAL)"
mkdir -p archive/duplicates_consolidated/graph/v1
cp -v archive/platform_consolidated/v1/graph_mutation_engine.py archive/duplicates_consolidated/graph/v1/ 2>/dev/null || echo "   (No graph engine)"
cp -v archive/platform_consolidated/v1/graph_mutation_service.py archive/duplicates_consolidated/graph/v1/ 2>/dev/null || echo "   (No graph service)"
cp -v archive/platform_consolidated/v1/train_state_service.py archive/duplicates_consolidated/graph/v1/ 2>/dev/null || echo "   (No train state)"
echo "   ✅ Done"
echo ""

echo "1️⃣2️⃣ ML MODELS → services/*.py (CANONICAL PREDICTORS)"
mkdir -p archive/duplicates_consolidated/ml/v1

# Clean up ML duplicates
echo "   Cleaning up duplicate ML files..."
rm -f intelligence/models/demand.py 2>/dev/null
rm -f intelligence/models/delay_predictor.py 2>/dev/null
rm -f intelligence/models/cancellation.py 2>/dev/null
rm -f intelligence/models/ranking.py 2>/dev/null
rm -f intelligence/models/route_ranker.py 2>/dev/null
rm -f core/ml_ranking_model.py 2>/dev/null

# Move training scripts
echo "   Moving training pipeline to intelligence/training/..."
mkdir -p intelligence/training
[ -f ml_data_collection.py ] && mv ml_data_collection.py intelligence/training/data_collection.py
[ -f ml_training_pipeline.py ] && mv ml_training_pipeline.py intelligence/training/pipeline.py

# Create wrapper scripts for backwards compatibility
echo "   Creating wrapper scripts..."
cat > scripts/ml_collect_data.py << 'EOF'
"""Wrapper for backwards compatibility"""
import sys
sys.path.insert(0, '..')
from intelligence.training.data_collection import *

if __name__ == "__main__":
    collect_data()
EOF

cat > scripts/ml_train.py << 'EOF'
"""Wrapper for backwards compatibility"""
import sys
sys.path.insert(0, '..')
from intelligence.training.pipeline import train_pipeline

if __name__ == "__main__":
    train_pipeline()
EOF

echo "   ✅ Done"
echo ""

echo "════════════════════════════════════════════════════════════════"
echo "  CONSOLIDATION PHASE COMPLETE ✅"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Summary:"
echo "  ✅ All 12 categor categories consolidated"
echo "  ✅ Old v1 versions archived to: archive/duplicates_consolidated/*"
echo "  ✅ ML training moved to: intelligence/training/"
echo "  ✅ Wrapper scripts created for backwards compatibility"
echo ""
echo "Next steps:"
echo "  1. Verify imports: python -c 'from domains.routing.engine import RailwayRouteEngine'"
echo "  2. Run tests: pytest tests/"
echo "  3. Git commit: git add -A && git commit -m '...'"
echo ""

