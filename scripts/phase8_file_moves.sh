#!/bin/bash
set -e

echo "🚀 Phase 8: Structure Cleanup - File Moves"
echo ""

# Phase 8.1: Core module moves
echo "📦 Phase 8.1: Moving core abstractions to core/..."
git mv src/flock/artifacts.py src/flock/core/artifacts.py
git mv src/flock/subscription.py src/flock/core/subscription.py
git mv src/flock/visibility.py src/flock/core/visibility.py
git mv src/flock/context_provider.py src/flock/core/context_provider.py
git mv src/flock/store.py src/flock/core/store.py
echo "✅ Core module moves complete (5 files)"
echo ""

# Phase 8.2: Orchestrator module moves
echo "📦 Phase 8.2: Moving orchestrator subsystems to orchestrator/..."
git mv src/flock/artifact_collector.py src/flock/orchestrator/artifact_collector.py
git mv src/flock/batch_accumulator.py src/flock/orchestrator/batch_accumulator.py
git mv src/flock/correlation_engine.py src/flock/orchestrator/correlation_engine.py
echo "✅ Orchestrator module moves complete (3 files)"
echo ""

# Phase 8.3: API module moves
echo "📦 Phase 8.3: Moving API layer to api/..."
git mv src/flock/service.py src/flock/api/service.py
git mv src/flock/api_models.py src/flock/api/models.py
echo "✅ API module moves complete (2 files)"
echo ""

# Phase 8.4: Models module creation
echo "📦 Phase 8.4: Creating models/ module..."
mkdir -p src/flock/models
git mv src/flock/system_artifacts.py src/flock/models/system_artifacts.py
echo "✅ Models module created (1 file)"
echo ""

# Phase 8.5: Utils consolidation
echo "📦 Phase 8.5: Consolidating utilities to utils/..."
git mv src/flock/utilities.py src/flock/utils/utilities.py
git mv src/flock/runtime.py src/flock/utils/runtime.py
git mv src/flock/helper/cli_helper.py src/flock/utils/cli_helper.py
echo "✅ Utils consolidation complete (3 files)"
echo ""

# Cleanup empty directories
echo "🧹 Cleaning up empty directories..."
rmdir src/flock/helper 2>/dev/null || echo "  (helper/ already removed)"
rmdir src/flock/utility 2>/dev/null || echo "  (utility/ already removed)"
echo ""

echo "✅ All file moves complete!"
echo "📊 Summary: 14 files moved, 2 directories cleaned up"
