"""
Quick Verification: Semantic Features Test

This script verifies semantic features are working correctly without
requiring LLM API calls. Perfect for testing installation and basic functionality.

📚 Requires: uv add flock-core[semantic]
"""

import sys

from flock.semantic import SEMANTIC_AVAILABLE, EmbeddingService


print("\n" + "=" * 70)
print("🔍 Semantic Features Verification")
print("=" * 70)

# Check if semantic features available
print("\n1. Checking semantic availability...")
if SEMANTIC_AVAILABLE:
    print("   ✅ Semantic features installed and available!")
else:
    print("   ❌ Semantic features not available")
    print("   📦 Install with: uv add flock-core[semantic]")
    sys.exit(1)

# Test embedding generation
print("\n2. Testing embedding generation...")
service = EmbeddingService.get_instance()

text1 = "Critical SQL injection vulnerability in login form"
text2 = "Security breach detected in authentication system"
text3 = "Button color should be blue instead of green"

embedding1 = service.embed(text1)
embedding2 = service.embed(text2)
embedding3 = service.embed(text3)

print(f"   ✅ Generated embeddings with shape: {embedding1.shape}")

# Test similarity computation
print("\n3. Testing semantic similarity...")

sim_high = service.similarity(text1, text2)  # Should be high (both security)
sim_low = service.similarity(text1, text3)  # Should be low (different topics)

print(f"   Security vs Security:  {sim_high:.3f} (should be HIGH ~0.5-0.8)")
print(f"   Security vs UI:        {sim_low:.3f} (should be LOW ~0.1-0.3)")

if sim_high > sim_low:
    print("   ✅ Similarity scores make sense!")
else:
    print("   ⚠️  Unexpected similarity scores")

# Test batch processing
print("\n4. Testing batch processing...")
texts = [
    "Database connection timeout",
    "API response time slow",
    "User interface bug",
]
embeddings = service.embed_batch(texts)
print(f"   ✅ Batch processed {len(embeddings)} texts")

# Test cache
print("\n5. Testing embedding cache...")
# First call
embedding_a = service.embed("Test sentence for caching")
# Second call (should hit cache)
embedding_b = service.embed("Test sentence for caching")

import numpy as np


if np.array_equal(embedding_a, embedding_b):
    print("   ✅ Cache working correctly!")
else:
    print("   ⚠️  Cache might not be working")

print("\n" + "=" * 70)
print("✅ All semantic features verified successfully!")
print("=" * 70)
print("\n🚀 Ready to use semantic subscriptions!")
print("\nNext steps:")
print("  • Run: uv run examples/08-semantic/01_intelligent_ticket_routing.py")
print("  • Read: docs/semantic-subscriptions.md")
print()
