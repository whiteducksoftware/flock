"""
🎓 Lesson 08: The Matchmaker - Correlated AND Gates with JoinSpec

CONCEPT: Sometimes data arrives separately but needs to be processed together.
JoinSpec lets you correlate related artifacts (like matching orders with shipments)
and ensures they're processed as a unit.

REAL-WORLD USE CASE:
E-commerce fulfillment center needs to match customer orders with shipping updates.
Both happen independently, but customer service needs BOTH to provide accurate updates.

KEY LEARNING:
- JoinSpec creates "correlated AND gates" - match artifacts by a common key
- `by=lambda x: x.order_id` defines the correlation key
- `within=timedelta(hours=24)` sets the correlation time window
- Agent only triggers when BOTH correlated artifacts arrive

WHY THIS MATTERS:
Without JoinSpec, you'd need complex state management and matching logic.
With JoinSpec, the orchestrator handles correlation automatically!

PROGRESSION NOTE:
You've learned: single agents (L01), chaining (L02), predicates (L03),
feedback loops (L04), tracing (L05), visibility (L06), parallelism (L07).
NOW: Correlated data processing!
"""

import asyncio
from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type
from flock.subscription import JoinSpec


@flock_type
class Order(BaseModel):
    order_id: str
    customer_name: str
    items: list[str]
    total_amount: float
    order_time: datetime = Field(default_factory=datetime.now)


@flock_type
class ShipmentUpdate(BaseModel):
    order_id: str  # ⭐ Correlation key - matches with Order.order_id
    tracking_number: str
    carrier: str
    estimated_delivery: str
    current_location: str


@flock_type
class CustomerNotification(BaseModel):
    customer_name: str
    order_summary: str
    shipping_status: str
    tracking_info: str
    estimated_arrival: str
    personalized_message: str


flock = Flock()

# 🔗 The Matchmaker Agent - Correlates orders with shipments using JoinSpec!
customer_service = (
    flock.agent("customer_service")
    .description(
        "Customer service agent that sends personalized notifications "
        "by correlating order details with shipping updates. Uses JoinSpec "
        "to ensure BOTH order and shipment data are available before notifying!"
    )
    .consumes(
        Order,
        ShipmentUpdate,
        join=JoinSpec(
            by=lambda x: x.order_id,  # ⭐ Correlation key
            within=timedelta(hours=24),  # ⭐ Time window for matching
        ),
    )
    .publishes(CustomerNotification)
)


async def main():
    """
    📖 LEARNING SCENARIO:

    1. Publish 3 orders
    2. Publish 2 shipment updates (only 2 matches possible)
    3. Watch JoinSpec correlate them by order_id
    4. See customer notifications generated ONLY for matched pairs

    ⚠️ KEY INSIGHT: Order #3 won't trigger notification (no shipment yet)!
    """

    print("🎯 LESSON 08: The Matchmaker - JoinSpec in Action")
    print("=" * 60)
    print("📦 E-Commerce Fulfillment Center Demo")
    print()
    print("🔍 CONCEPT: Correlating related data streams")
    print("   - Orders arrive from customers")
    print("   - Shipment updates arrive from warehouse")
    print("   - JoinSpec matches them by order_id")
    print("   - Notification only fires when BOTH arrive!\n")

    # Step 1: Publish orders from customers
    print("=" * 60)
    print("📋 STEP 1: Customer Orders Arriving...")
    print("=" * 60)

    orders = [
        Order(
            order_id="ORD-001",
            customer_name="Alice Johnson",
            items=["Laptop", "Mouse", "USB Cable"],
            total_amount=1299.99,
        ),
        Order(
            order_id="ORD-002",
            customer_name="Bob Smith",
            items=["Headphones", "Phone Case"],
            total_amount=149.99,
        ),
        Order(
            order_id="ORD-003",
            customer_name="Carol Williams",
            items=["Keyboard", "Monitor"],
            total_amount=599.99,
        ),
    ]

    for order in orders:
        print(f"   🛒 Order {order.order_id}: {order.customer_name} - ${order.total_amount:.2f}")
        await flock.publish(order)

    await flock.run_until_idle()
    print("\n   ⏳ Orders received, waiting for shipment updates...")

    # Step 2: Publish shipment updates (only 2 of 3!)
    print("\n" + "=" * 60)
    print("📦 STEP 2: Shipment Updates from Warehouse...")
    print("=" * 60)

    shipments = [
        ShipmentUpdate(
            order_id="ORD-001",  # ✅ Matches Alice's order
            tracking_number="TRK-12345",
            carrier="FedEx",
            estimated_delivery="Oct 15, 2025",
            current_location="Distribution Center - Portland, OR",
        ),
        ShipmentUpdate(
            order_id="ORD-002",  # ✅ Matches Bob's order
            tracking_number="TRK-67890",
            carrier="UPS",
            estimated_delivery="Oct 14, 2025",
            current_location="Out for Delivery - Seattle, WA",
        ),
        # ⚠️ Notice: No shipment for ORD-003 yet!
    ]

    for shipment in shipments:
        print(
            f"   📮 Shipment for {shipment.order_id}: {shipment.carrier} - {shipment.current_location}"
        )
        await flock.publish(shipment)

    print("\n   🔗 JoinSpec is correlating orders with shipments...")
    await flock.run_until_idle()

    # Step 3: Check results
    notifications = await flock.store.get_by_type(CustomerNotification)

    print("\n" + "=" * 60)
    print("📧 STEP 3: Customer Notifications Generated")
    print("=" * 60)

    if not notifications:
        print("   ⚠️ No notifications generated yet!")

    for i, notif in enumerate(notifications, 1):
        print(f"\n📬 Notification #{i}:")
        print(f"   Customer: {notif.customer_name}")
        print(f"   Order: {notif.order_summary}")
        print(f"   Shipping: {notif.shipping_status}")
        print(f"   Tracking: {notif.tracking_info}")
        print(f"   Arrival: {notif.estimated_arrival}")
        print(f"   Message: {notif.personalized_message[:100]}...")

    # Step 4: Analysis
    print("\n" + "=" * 60)
    print("📊 ANALYSIS: JoinSpec in Action")
    print("=" * 60)
    print(f"   Orders published: {len(orders)}")
    print(f"   Shipments published: {len(shipments)}")
    print(f"   Notifications sent: {len(notifications)}")
    print()
    print("   💡 KEY INSIGHTS:")
    print("   1️⃣  JoinSpec matched orders with shipments by order_id")
    print("   2️⃣  Only 2 notifications sent (ORD-001, ORD-002 matched)")
    print("   3️⃣  ORD-003 didn't trigger (no shipment update yet)")
    print("   4️⃣  Agent received BOTH artifacts together for processing")
    print()
    print("🎓 LESSON COMPLETE!")
    print()
    print("🔬 EXPERIMENTS TO TRY:")
    print("   1. Publish shipment for ORD-003 and watch it match")
    print("   2. Change time window to `within=timedelta(seconds=5)`")
    print("   3. Add a third artifact type (e.g., WarehouseAlert)")
    print("   4. Use predicate `where=` to filter high-value orders")
    print()
    print("➡️  NEXT: Lesson 09 - The Batch Optimizer (BatchSpec)")


if __name__ == "__main__":
    asyncio.run(main())
