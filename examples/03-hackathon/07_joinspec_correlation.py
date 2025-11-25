"""
Hackathon Track 07: JoinSpec - Correlating Multiple Artifact Types

🎓 LEARNING OBJECTIVE:
Learn how to correlate multiple artifact types that belong together.
JoinSpec waits for related artifacts before processing them together.

KEY CONCEPTS:
- JoinSpec for correlating artifacts
- Key-based correlation (by=lambda)
- Time windows (within=timedelta)
- Waiting for multiple related inputs

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio
from datetime import timedelta

from pydantic import BaseModel, Field

from flock import Flock
from flock.core.subscription import JoinSpec
from flock.registry import flock_type


# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


# ============================================================================
# STEP 1: Define Related Types
# ============================================================================
# JoinSpec is used when you need MULTIPLE artifact types that are related.
# They share a common identifier (like order_id, patient_id, etc.)
# ============================================================================

@flock_type
class Order(BaseModel):
    """An e-commerce order."""
    order_id: str = Field(description="Unique order identifier")
    customer_id: str
    items: list[dict[str, str]] = Field(description="Ordered items")
    total_amount: float


@flock_type
class Payment(BaseModel):
    """Payment information for an order."""
    order_id: str = Field(description="Order this payment is for")
    payment_method: str
    amount: float
    transaction_id: str
    status: str = Field(description="Payment status: pending, completed, failed")


@flock_type
class ShippingInfo(BaseModel):
    """Shipping details for an order."""
    order_id: str = Field(description="Order this shipping is for")
    address: str
    carrier: str
    tracking_number: str
    estimated_delivery: str


@flock_type
class OrderConfirmation(BaseModel):
    """Complete order confirmation with all details."""
    order_id: str
    customer_id: str
    items: list[dict[str, str]]
    payment_status: str
    shipping_carrier: str
    tracking_number: str
    total_amount: float
    confirmation_message: str


# ============================================================================
# STEP 2: Create the Orchestrator
# ============================================================================

flock = Flock()


# ============================================================================
# STEP 3: Define Agent with JoinSpec
# ============================================================================
# JoinSpec correlates artifacts by a common key.
# The agent waits for ALL required types with matching keys before executing.
#
# Syntax:
#   .consumes(Type1, Type2, join=JoinSpec(
#       by=lambda x: x.order_id,
#       within=timedelta(minutes=5)
#   ))
#
# Key points:
# - Agent needs ALL types before executing
# - Artifacts must have matching keys (order_id in this case)
# - Time window ensures artifacts arrive within reasonable time
# ============================================================================

# This agent waits for Order, Payment, AND ShippingInfo with matching order_id
order_processor = (
    flock.agent("order_processor")
    .description(
        "Processes complete orders by correlating order, payment, and shipping information. "
        "Only processes when all three pieces of information are available for the same order."
    )
    .consumes(
        Order,
        Payment,
        ShippingInfo,
        join=JoinSpec(
            # IMPORTANT:
            # - JoinSpec.by receives ONE payload instance at a time
            # - It must return the correlation key (here: order_id)
            by=lambda artifact: artifact.order_id,
            within=timedelta(minutes=5),  # All must arrive within 5 minutes
        ),
    )
    .publishes(OrderConfirmation)
)


# ============================================================================
# STEP 4: Run with Correlated Artifacts
# ============================================================================

async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    print("=" * 70)
    print("🔗 JOINSPEC EXAMPLE - Order Processing with Correlation")
    print("=" * 70)
    print()
    
    # Order 1: All pieces arrive together
    print("📦 Order #001: Publishing all pieces together...")
    await flock.publish(Order(
        order_id="ORD-001",
        customer_id="CUST-123",
        items=[{"name": "Laptop", "quantity": "1"}],
        total_amount=999.99
    ))
    await flock.publish(Payment(
        order_id="ORD-001",
        payment_method="credit_card",
        amount=999.99,
        transaction_id="TXN-001",
        status="completed"
    ))
    await flock.publish(ShippingInfo(
        order_id="ORD-001",
        address="123 Main St, City, State 12345",
        carrier="FedEx",
        tracking_number="FX123456789",
        estimated_delivery="2025-01-15"
    ))
    
    # Order 2: Pieces arrive in different order
    print("\n📦 Order #002: Publishing pieces in different order...")
    await flock.publish(ShippingInfo(
        order_id="ORD-002",
        address="456 Oak Ave, City, State 67890",
        carrier="UPS",
        tracking_number="UPS987654321",
        estimated_delivery="2025-01-16"
    ))
    await flock.publish(Order(
        order_id="ORD-002",
        customer_id="CUST-456",
        items=[{"name": "Mouse", "quantity": "2"}],
        total_amount=49.98
    ))
    await flock.publish(Payment(
        order_id="ORD-002",
        payment_method="paypal",
        amount=49.98,
        transaction_id="TXN-002",
        status="completed"
    ))
    
    # Order 3: Missing payment (won't process!)
    print("\n📦 Order #003: Publishing order and shipping (payment missing)...")
    await flock.publish(Order(
        order_id="ORD-003",
        customer_id="CUST-789",
        items=[{"name": "Keyboard", "quantity": "1"}],
        total_amount=79.99
    ))
    await flock.publish(ShippingInfo(
        order_id="ORD-003",
        address="789 Pine Rd, City, State 11111",
        carrier="USPS",
        tracking_number="USPS111222333",
        estimated_delivery="2025-01-17"
    ))
    # Payment is missing - order won't be processed!
    
    print("\n⏳ Processing orders with JoinSpec correlation...")
    print()
    
    # Run until completion
    await flock.run_until_idle()
    
    # Check results
    confirmations = await flock.store.get_by_type(OrderConfirmation)
    
    print("=" * 70)
    print("📊 CORRELATION RESULTS")
    print("=" * 70)
    
    print(f"\n✅ Orders Processed: {len(confirmations)}")
    print(f"   (Expected: 2 - Order #001 and #002)")
    print(f"   (Order #003 missing payment, so not processed)")
    print()
    
    for conf in confirmations:
        print(f"📦 Order {conf.order_id}:")
        print(f"   Customer: {conf.customer_id}")
        print(f"   Payment: {conf.payment_status}")
        print(f"   Shipping: {conf.shipping_carrier} ({conf.tracking_number})")
        print(f"   Total: ${conf.total_amount:.2f}")
        print(f"   Message: {conf.confirmation_message[:60]}...")
        print()
    
    print("=" * 70)
    print("💡 Key Insights:")
    print("   - Order #001: All pieces arrived → Processed ✅")
    print("   - Order #002: All pieces arrived (different order) → Processed ✅")
    print("   - Order #003: Missing payment → NOT processed ❌")
    print("   - JoinSpec waits for ALL types with matching order_id")
    print("   - Order of arrival doesn't matter!")


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface"""
    print("🌐 Starting Flock Dashboard...")
    print("   Visit http://localhost:8344 to see JoinSpec correlation!")
    print()
    print("💡 Watch how the agent waits for all related artifacts!")
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())


# ============================================================================
# 🎓 NOW IT'S YOUR TURN!
# ============================================================================
# 
# EXPERIMENT 1: Different Correlation Keys
# -----------------------------------------
# Correlate by customer_id instead of order_id:
#   customer_analyzer = (
#       flock.agent("customer_analyzer")
#       .consumes(
#           Order,
#           Payment,
#           join=JoinSpec(
#               by=lambda order, payment: order.customer_id == payment.customer_id
#           )
#       )
#       .publishes(CustomerAnalysis)
#   )
#
# What happens if one customer has multiple orders?
#
#
# EXPERIMENT 2: Time Window Testing
# ----------------------------------
# Test the time window constraint:
#   order_processor = (
#       flock.agent("order_processor")
#       .consumes(
#           Order, Payment, ShippingInfo,
#           join=JoinSpec(
#               by=lambda o, p, s: o.order_id == p.order_id == s.order_id,
#               within=timedelta(seconds=10)  # Very short window!
#           )
#       )
#       .publishes(OrderConfirmation)
#   )
#
# Publish Order and Payment, wait 15 seconds, then publish ShippingInfo.
# Does it still process? What if you publish all within 5 seconds?
#
#
# EXPERIMENT 3: Two-Type Join
# ---------------------------
# Join just two types:
#   order_payment_processor = (
#       flock.agent("order_payment_processor")
#       .consumes(
#           Order,
#           Payment,
#           join=JoinSpec(
#               by=lambda order, payment: order.order_id == payment.order_id
#           )
#       )
#       .publishes(OrderConfirmation)
#   )
#
# This processes orders as soon as payment arrives (no shipping needed).
# When would this be useful?
#
#
# EXPERIMENT 4: Multiple Correlation Keys
# ----------------------------------------
# Correlate by BOTH order_id AND customer_id:
#   strict_processor = (
#       flock.agent("strict_processor")
#       .consumes(
#           Order, Payment,
#           join=JoinSpec(
#               by=lambda order, payment: (
#                   order.order_id == payment.order_id and
#                   order.customer_id == payment.customer_id
#               )
#           )
#       )
#       .publishes(OrderConfirmation)
#   )
#
# Why might you want to check both?
#
#
# EXPERIMENT 5: JoinSpec + Conditional Filtering
# ------------------------------------------------
# Combine JoinSpec with where clauses:
#   premium_order_processor = (
#       flock.agent("premium_order_processor")
#       .consumes(
#           Order,
#           Payment,
#           ShippingInfo,
#           join=JoinSpec(
#               by=lambda o, p, s: o.order_id == p.order_id == s.order_id
#           ),
#           where=lambda order, payment, shipping: order.total_amount >= 100
#       )
#       .publishes(OrderConfirmation)
#   )
#
# This only processes orders over $100!
#
#
# EXPERIMENT 6: Medical Diagnostics Pattern
# ------------------------------------------
# Create a medical diagnostics system:
#   @flock_type
#   class LabResults(BaseModel):
#       patient_id: str
#       test_type: str
#       results: dict
#
#   @flock_type
#   class XRayImage(BaseModel):
#       patient_id: str
#       exam_type: str
#       image_data: str
#
#   radiologist = (
#       flock.agent("radiologist")
#       .consumes(
#           LabResults,
#           XRayImage,
#           join=JoinSpec(
#               by=lambda lab, xray: lab.patient_id == xray.patient_id,
#               within=timedelta(hours=24)
#           )
#       )
#       .publishes(Diagnosis)
#   )
#
# Why is the time window important here?
#
#
# CHALLENGE: Build a Complete E-Commerce System
# -----------------------------------------------
# Design a full order processing system:
#   1. Order created → Order artifact
#   2. Payment processed → Payment artifact (correlates with Order)
#   3. Inventory checked → InventoryStatus artifact (correlates with Order)
#   4. Shipping label created → ShippingInfo artifact (correlates with Order)
#   5. Order processor waits for ALL four (JoinSpec)
#   6. Only processes if: payment=completed AND inventory=available
#
# How do you handle partial failures? What if payment fails but shipping succeeds?
# Use conditional filtering to handle edge cases!
#
# ============================================================================
