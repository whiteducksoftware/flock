"""
BatchSpec Example: E-commerce Order Batch Processing (Dashboard)

Real-world scenario: Online store batches payment processing to reduce
transaction fees. Instead of processing one order at a time ($0.30/transaction),
batch 25 orders together for bulk discount ($0.10/transaction).

Cost savings: 25 orders × $0.20 saved = $5.00 per batch!

📊 Dashboard Features:
- Watch orders accumulate in real-time
- See batch size threshold approaching
- Visualize cost savings per batch
- Monitor timeout-based flushes
"""

import asyncio
from datetime import timedelta

from pydantic import BaseModel, Field

from flock.orchestrator import Flock
from flock.registry import flock_type
from flock.subscription import BatchSpec


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
        "Batches up to 25 orders or flushes every 30 seconds. "
        "Each batch saves $5.00 in transaction fees!"
    )
    .consumes(
        Order,
        batch=BatchSpec(
            size=25,  # Flush when 25 orders accumulated
            timeout=timedelta(seconds=10),  # OR flush every 30 seconds
        ),
    )
    .publishes(PaymentBatch)
)

# Start dashboard and publish orders to see batching in action!
# Try publishing 25 orders quickly to hit size threshold
# Or publish fewer and wait for 30-second timeout
asyncio.run(flock.serve(dashboard=True), debug=True)
