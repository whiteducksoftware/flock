"""
Getting Started: E-commerce Batch Processing

This example demonstrates BatchSpec: grouping multiple artifacts (orders)
together for efficient batch processing to reduce costs.

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio
from datetime import timedelta

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type
from flock.core.subscription import BatchSpec

# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


@flock_type
class Order(BaseModel):
    order_id: str
    customer_name: str
    amount: float = Field(description="Order total in USD")
    payment_method: str
    priority: str = Field(default="normal", description="normal or express")


@flock_type
class PaymentBatch(BaseModel):
    batch_id: str
    order_count: int
    total_amount: float
    transaction_fee: float
    savings: float = Field(description="Money saved by batching")
    processing_time: str


flock = Flock()

# Payment processor waits for 25 orders OR 30 seconds (whichever comes first)
payment_processor = (
    flock.agent("payment_processor")
    .description(
        "Processes payment batches to minimize transaction fees. "
        "Batches up to 25 orders or flushes every 30 seconds."
    )
    .consumes(
        Order,
        batch=BatchSpec(
            size=25,  # Flush when 25 orders accumulated
            timeout=timedelta(seconds=30),  # OR flush every 30 seconds
        ),
    )
    .publishes(PaymentBatch)
)


async def simulate_orders(flock: Flock, count: int):
    """Simulate incoming orders"""
    for i in range(1, count + 1):
        order = Order(
            order_id=f"ORD-{i:04d}",
            customer_name=f"Customer-{i}",
            amount=round(25.99 + (i * 5.5), 2),
            payment_method="credit_card",
            priority="normal" if i % 5 != 0 else "express",
        )
        await flock.publish(order)

        # Print progress every 5 orders
        if i % 5 == 0:
            print(f"   📦 Received {i} orders...")


async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    print("🛒 E-Commerce Batch Payment Processing")
    print("=" * 60)
    print("💰 Cost Optimization: Batching reduces transaction fees!\n")

    print("📊 Pricing:")
    print("   ❌ Single transaction: $0.30 per order")
    print("   ✅ Batch transaction:  $0.10 per order (25+ orders)")
    print("   💵 Savings:            $0.20 per order x 25 = $5.00/batch\n")

    print("⚙️  Batch Configuration:")
    print("   📦 Size threshold:  25 orders")
    print("   ⏱️  Timeout:         30 seconds")
    print("   🏃 Whichever comes first!\n")

    # Scenario 1: SIZE THRESHOLD TRIGGER (25 orders = full batch)
    print("=" * 60)
    print("🎯 SCENARIO 1: Size Threshold (25 orders)")
    print("=" * 60)
    print("📥 Publishing 25 orders quickly...\n")

    await simulate_orders(flock, 25)

    print("\n⚡ Size threshold reached! Processing batch...")
    await flock.run_until_idle()

    # Scenario 2: PARTIAL BATCH + TIMEOUT (only 10 orders, wait for timeout)
    print("\n" + "=" * 60)
    print("🎯 SCENARIO 2: Timeout Trigger (partial batch)")
    print("=" * 60)
    print("📥 Publishing 10 more orders...\n")

    await simulate_orders(flock, 10)

    print("\n⏳ Only 10 orders (not enough for size=25)...")
    print("   Waiting for 30-second timeout...\n")

    # Wait for timeout
    await asyncio.sleep(2)  # Simulate some time passing
    print("   ⏰ Timeout approaching...")
    await asyncio.sleep(1)

    # Manually trigger timeout check (in production, this happens automatically)
    await flock._check_batch_timeouts()
    await flock.run_until_idle()

    # Retrieve payment batches
    batches = await flock.store.get_by_type(PaymentBatch)

    print("\n" + "=" * 60)
    print("💳 PAYMENT BATCHES PROCESSED:")
    print("=" * 60)

    total_savings = 0.0
    for i, batch in enumerate(batches, 1):
        print(f"\n📦 Batch #{i} ({batch.batch_id}):")
        print(f"   Orders:          {batch.order_count}")
        print(f"   Total Amount:    ${batch.total_amount:,.2f}")
        print(f"   Transaction Fee: ${batch.transaction_fee:.2f}")
        print(f"   💰 Savings:      ${batch.savings:.2f}")
        print(f"   Processing Time: {batch.processing_time}")
        total_savings += batch.savings

    print("\n" + "=" * 60)
    print(f"✅ Total Batches Processed: {len(batches)}")
    print(f"💵 TOTAL SAVINGS: ${total_savings:.2f}")
    print("\n💡 KEY FEATURE: BatchSpec optimizes costs by batching!")
    print("   Size threshold OR timeout - whichever comes first wins!")


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface"""
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())
