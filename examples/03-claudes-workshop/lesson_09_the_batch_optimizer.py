"""
🎓 Lesson 09: The Batch Optimizer - Efficient Processing with BatchSpec

CONCEPT: Processing items one-at-a-time is inefficient. BatchSpec lets you
accumulate artifacts and process them in optimal batches - triggered by
either SIZE threshold or TIMEOUT, whichever comes first!

REAL-WORLD USE CASE:
Payment processor wants to batch transactions to reduce fees. Processing one
transaction costs $0.30, but batching 25 together costs only $0.10 each.
Savings: $0.20 × 25 = $5.00 per batch!

KEY LEARNING:
- BatchSpec(size=25, timeout=30s) means "batch 25 items OR wait 30 seconds"
- SIZE trigger: Batch flushes immediately when threshold reached
- TIMEOUT trigger: Partial batches flush after timeout (no items lost!)
- Agent receives list of artifacts, not individual items

WHY THIS MATTERS:
Batching is critical for:
- Cost optimization (transaction fees, API rate limits)
- Performance (bulk database writes, batch ML inference)
- Network efficiency (fewer HTTP requests)

PROGRESSION NOTE:
You've learned: chaining (L02), predicates (L03), correlation (L08).
NOW: Efficient batch processing with automatic flushing!
"""

import asyncio
from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type
from flock.subscription import BatchSpec


@flock_type
class Transaction(BaseModel):
    transaction_id: str
    customer_id: str
    amount: float = Field(gt=0.0, description="Transaction amount in USD")
    payment_method: str
    timestamp: datetime = Field(default_factory=datetime.now)


@flock_type
class PaymentBatchReport(BaseModel):
    batch_id: str
    transaction_count: int
    total_amount: float
    individual_fee_cost: float  # Cost if processed individually
    batch_fee_cost: float  # Actual cost with batching
    savings: float  # Money saved!
    processing_time: str
    flush_reason: str  # "size_threshold" or "timeout"


flock = Flock()

# 💰 The Batch Optimizer - Processes payments in cost-efficient batches!
payment_processor = (
    flock.agent("payment_processor")
    .description(
        "Payment processor that batches transactions to minimize fees. "
        "Uses BatchSpec to accumulate 25 transactions OR flush after 30 seconds. "
        "Each batch saves $5.00 in transaction fees - efficiency at its finest!"
    )
    .consumes(
        Transaction,
        batch=BatchSpec(
            size=25,  # ⭐ Flush when 25 transactions accumulated
            timeout=timedelta(seconds=30),  # ⭐ OR flush after 30 seconds
        ),
    )
    .publishes(PaymentBatchReport)
)


async def main():
    """
    📖 LEARNING SCENARIO:

    Scenario 1: SIZE THRESHOLD
    - Publish 25 transactions quickly
    - Watch batch flush immediately when size=25 reached

    Scenario 2: TIMEOUT TRIGGER
    - Publish 10 transactions (not enough for size threshold)
    - Wait for 30-second timeout
    - Watch partial batch flush automatically

    💡 KEY INSIGHT: No transactions are lost! Timeout ensures everything processes.
    """

    print("🎯 LESSON 09: The Batch Optimizer - BatchSpec in Action")
    print("=" * 60)
    print("💰 Payment Processing Optimization Demo")
    print()
    print("💵 PRICING MODEL:")
    print("   ❌ Individual: $0.30 per transaction")
    print("   ✅ Batch (25+): $0.10 per transaction")
    print("   💎 Savings:    $0.20 per transaction")
    print("   🎯 Max Batch:  $5.00 saved per 25 transactions!\n")

    print("⚙️  BATCH CONFIGURATION:")
    print("   📦 Size Threshold: 25 transactions")
    print("   ⏱️  Timeout:        30 seconds")
    print("   🏃 Whichever comes first wins!\n")

    # Scenario 1: SIZE THRESHOLD TRIGGER
    print("=" * 60)
    print("🎯 SCENARIO 1: Size Threshold (25 transactions)")
    print("=" * 60)
    print("📥 Publishing 25 transactions rapidly...\n")

    # Simulate 25 transactions arriving quickly
    for i in range(1, 26):
        transaction = Transaction(
            transaction_id=f"TXN-{i:04d}",
            customer_id=f"CUST-{(i % 10) + 1:03d}",
            amount=round(25.99 + (i * 3.75), 2),
            payment_method="credit_card",
        )
        await flock.publish(transaction)

        # Progress indicator every 5 transactions
        if i % 5 == 0:
            print(f"   💳 {i}/25 transactions received...")

    print("\n   ⚡ Size threshold reached (25 transactions)!")
    print("   🔄 Batch flushing immediately...\n")

    await flock.run_until_idle()

    # Check first batch report
    reports = await flock.store.get_by_type(PaymentBatchReport)

    if reports:
        report = reports[0]
        print(f"✅ Batch #{1} Processed:")
        print(f"   Transactions: {report.transaction_count}")
        print(f"   Total Amount: ${report.total_amount:,.2f}")
        print(f"   Individual Fee: ${report.individual_fee_cost:.2f}")
        print(f"   Batch Fee: ${report.batch_fee_cost:.2f}")
        print(f"   💰 Savings: ${report.savings:.2f}")
        print(f"   Flush Reason: {report.flush_reason}")

    # Scenario 2: TIMEOUT TRIGGER (partial batch)
    print("\n" + "=" * 60)
    print("🎯 SCENARIO 2: Timeout Trigger (partial batch)")
    print("=" * 60)
    print("📥 Publishing 10 more transactions...\n")

    # Simulate 10 more transactions (not enough for size=25)
    for i in range(26, 36):
        transaction = Transaction(
            transaction_id=f"TXN-{i:04d}",
            customer_id=f"CUST-{(i % 10) + 1:03d}",
            amount=round(25.99 + (i * 3.75), 2),
            payment_method="credit_card",
        )
        await flock.publish(transaction)

        if (i - 25) % 5 == 0:
            print(f"   💳 {i - 25}/10 transactions received...")

    print("\n   ⏳ Only 10 transactions (not enough for size=25)...")
    print("   ⌛ Waiting for 30-second timeout to flush partial batch...")
    print("   (Simulating timeout with manual trigger)\n")

    # In production, timeout happens automatically
    # For demo, we'll manually trigger it
    await asyncio.sleep(1)  # Brief pause for effect
    print("   ⏰ Timeout reached! Flushing partial batch...")

    # Manually trigger timeout (in production this is automatic)
    await flock._check_batch_timeouts()
    await flock.run_until_idle()

    # Check second batch report
    reports = await flock.store.get_by_type(PaymentBatchReport)

    if len(reports) >= 2:
        report = reports[1]
        print(f"\n✅ Batch #{2} Processed:")
        print(f"   Transactions: {report.transaction_count}")
        print(f"   Total Amount: ${report.total_amount:,.2f}")
        print(f"   Individual Fee: ${report.individual_fee_cost:.2f}")
        print(f"   Batch Fee: ${report.batch_fee_cost:.2f}")
        print(f"   💰 Savings: ${report.savings:.2f}")
        print(f"   Flush Reason: {report.flush_reason}")

    # Final Analysis
    print("\n" + "=" * 60)
    print("📊 FINAL ANALYSIS")
    print("=" * 60)

    total_transactions = 35
    total_savings = sum(r.savings for r in reports)

    print(f"   Total Transactions: {total_transactions}")
    print(f"   Batches Processed: {len(reports)}")
    print(f"   💰 TOTAL SAVINGS: ${total_savings:.2f}")
    print()
    print("   💡 KEY INSIGHTS:")
    print("   1️⃣  Batch #1 flushed on SIZE (25 transactions)")
    print("   2️⃣  Batch #2 flushed on TIMEOUT (10 transactions)")
    print("   3️⃣  No transactions lost - timeout ensures delivery!")
    print("   4️⃣  Agent received batches as lists, not individual items")
    print()
    print("🎓 LESSON COMPLETE!")
    print()
    print("🔬 EXPERIMENTS TO TRY:")
    print("   1. Change size to 50 and see how timeout catches partial batches")
    print("   2. Add predicate `where=lambda x: x.amount > 100` for high-value only")
    print("   3. Combine with visibility for tenant-specific batching")
    print("   4. Add second agent that processes PaymentBatchReport")
    print()
    print("➡️  NEXT: Lesson 10 - The Smart Factory (JoinSpec + BatchSpec combined!)")


if __name__ == "__main__":
    asyncio.run(main())
