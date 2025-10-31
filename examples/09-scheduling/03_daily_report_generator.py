"""
Timer Scheduling: Daily Report Generator

This example demonstrates time-based scheduling - running at a specific time daily.
A report generator runs every day at 5 PM to summarize transaction data.

KEY CONCEPTS:
- schedule(at=time(hour, minute)) for daily execution at specific time
- Aggregates data from artifacts on the blackboard
- Useful for end-of-day reports, daily summaries, scheduled notifications

PATTERN: Time-Based Scheduling (Daily)
USE CASE: Daily reports, scheduled backups, end-of-day processing
"""

import asyncio
import random
from datetime import date, datetime, time, timedelta

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type
from flock.utils.runtime import Context


# ============================================================================
# CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


# ============================================================================
# TYPE REGISTRATION: Define artifact types
# ============================================================================
@flock_type
class Transaction(BaseModel):
    """A financial transaction record"""

    transaction_id: str = Field(description="Unique transaction identifier")
    amount: float = Field(description="Transaction amount in dollars")
    user_id: str = Field(description="User who made the transaction")
    category: str = Field(description="Transaction category (food, travel, etc)")
    timestamp: datetime = Field(description="When the transaction occurred")
    status: str = Field(description="Transaction status (pending, completed, failed)")


@flock_type
class DailyReport(BaseModel):
    """End-of-day financial report"""

    report_date: date = Field(description="Date this report covers")
    total_transactions: int = Field(description="Total number of transactions")
    total_revenue: float = Field(description="Total revenue in dollars")
    avg_transaction: float = Field(description="Average transaction amount")
    completed_count: int = Field(description="Number of completed transactions")
    failed_count: int = Field(description="Number of failed transactions")
    top_category: str = Field(description="Category with most transactions")
    summary: str = Field(description="AI-generated daily summary")
    generated_at: datetime = Field(description="When report was generated")


# ============================================================================
# AGENT SETUP: Create transaction processor and daily reporter
# ============================================================================
flock = Flock("openai/gpt-4o-mini")

# Agent 1: Process transactions (simulated - runs every 15 seconds for demo)
# In production, this would be triggered by actual transactions
transaction_processor = (
    flock.agent("transaction_processor")
    .description(
        "Processes incoming transactions from users. "
        "Validates, records, and publishes transaction data."
    )
    .schedule(every=timedelta(seconds=15))  # Frequent for demo purposes
    .publishes(Transaction)
)


# Agent 2: Generate daily report at 5 PM
# For demo purposes, we'll use a short interval instead
# In production: .schedule(at=time(hour=17, minute=0))
DEMO_MODE = True  # Set to False to use actual 5 PM schedule

if DEMO_MODE:
    # Run every 2 minutes for demo
    daily_reporter = (
        flock.agent("daily_reporter")
        .description(
            "Generates end-of-day financial report. "
            "Analyzes all transactions and creates summary."
        )
        .schedule(every=timedelta(minutes=2))  # Demo: every 2 minutes
        .consumes(Transaction)
        .publishes(DailyReport)
    )
else:
    # Production: run every day at 5 PM
    daily_reporter = (
        flock.agent("daily_reporter")
        .description(
            "Generates end-of-day financial report at 5 PM daily. "
            "Analyzes all transactions and creates summary."
        )
        .schedule(at=time(hour=17, minute=0))  # Every day at 5 PM
        .consumes(Transaction)
        .publishes(DailyReport)
    )


# ============================================================================
# AGENT IMPLEMENTATIONS
# ============================================================================
@transaction_processor.implement
async def process_transactions(ctx: Context) -> list[Transaction]:
    """
    Simulate processing incoming transactions.

    In production, this would:
    - Receive transactions from payment gateway
    - Validate transaction data
    - Update database
    - Publish to blackboard for reporting
    """
    # Generate random transactions
    categories = ["food", "travel", "entertainment", "shopping", "utilities"]
    statuses = ["completed", "completed", "completed", "pending", "failed"]
    users = [f"user_{i:03d}" for i in range(1, 21)]

    num_transactions = random.randint(2, 6)
    transactions = []

    for i in range(num_transactions):
        txn_id = f"TXN_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}"
        transactions.append(
            Transaction(
                transaction_id=txn_id,
                amount=round(random.uniform(5.0, 500.0), 2),
                user_id=random.choice(users),
                category=random.choice(categories),
                timestamp=datetime.now(),
                status=random.choice(statuses),
            )
        )

    print(f"[Transaction Processor] Processed {len(transactions)} transactions")
    return transactions


@daily_reporter.implement
async def generate_daily_report(ctx: Context) -> DailyReport:
    """
    Generate end-of-day financial report.

    Time-Based Scheduling:
    - ctx.trigger_type = "timer"
    - ctx.fire_time = scheduled time (e.g., 5:00 PM)
    - ctx.artifacts = [] (timer trigger)
    - Aggregates ALL transactions from blackboard
    """
    assert ctx.trigger_type == "timer"
    assert ctx.artifacts == []

    # Get all transactions from blackboard
    all_transactions = ctx.get_artifacts(Transaction)

    print()
    print("=" * 70)
    print(f"[Daily Reporter] Generating report - Iteration {ctx.timer_iteration}")
    print(f"[Daily Reporter] Fire time: {ctx.fire_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[Daily Reporter] Analyzing {len(all_transactions)} transactions")
    print("=" * 70)

    if not all_transactions:
        return DailyReport(
            report_date=date.today(),
            total_transactions=0,
            total_revenue=0.0,
            avg_transaction=0.0,
            completed_count=0,
            failed_count=0,
            top_category="N/A",
            summary="No transactions to report for this period.",
            generated_at=datetime.now(),
        )

    # Calculate statistics
    total_transactions = len(all_transactions)
    total_revenue = sum(t.amount for t in all_transactions if t.status == "completed")
    completed_transactions = [t for t in all_transactions if t.status == "completed"]
    failed_transactions = [t for t in all_transactions if t.status == "failed"]

    avg_transaction = (
        total_revenue / len(completed_transactions) if completed_transactions else 0.0
    )

    # Find top category
    category_counts = {}
    for txn in all_transactions:
        category_counts[txn.category] = category_counts.get(txn.category, 0) + 1
    top_category = (
        max(category_counts.items(), key=lambda x: x[1])[0]
        if category_counts
        else "N/A"
    )

    # Print summary
    print("\nReport Summary:")
    print(f"  Total Revenue: ${total_revenue:,.2f}")
    print(f"  Completed: {len(completed_transactions)}")
    print(f"  Failed: {len(failed_transactions)}")
    print(f"  Avg Transaction: ${avg_transaction:.2f}")
    print(f"  Top Category: {top_category}")

    # Generate AI summary
    summary_prompt = f"""Generate a concise daily financial report summary.

Metrics:
- Total transactions: {total_transactions}
- Total revenue: ${total_revenue:,.2f}
- Average transaction: ${avg_transaction:.2f}
- Completed: {len(completed_transactions)}
- Failed: {len(failed_transactions)}
- Top category: {top_category}

Provide 2-3 sentences highlighting key insights and trends."""

    print("\nGenerating AI summary...")

    return DailyReport(
        report_date=date.today(),
        total_transactions=total_transactions,
        total_revenue=round(total_revenue, 2),
        avg_transaction=round(avg_transaction, 2),
        completed_count=len(completed_transactions),
        failed_count=len(failed_transactions),
        top_category=top_category,
        summary=summary_prompt,  # LLM will expand
        generated_at=datetime.now(),
    )


# ============================================================================
# RUN: Execute the orchestrator
# ============================================================================
async def main_cli():
    """
    CLI mode: Demonstrate time-based scheduling

    Flow:
    1. transaction_processor runs every 15s, publishes transactions
    2. daily_reporter runs every 2 minutes (demo) or 5 PM (production)
    3. Demo runs for 5 minutes to show 2-3 report cycles
    """
    print("=" * 70)
    print("DAILY REPORT GENERATOR - Time-Based Scheduling Demo")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%H:%M:%S')}")
    print()

    if DEMO_MODE:
        print("DEMO MODE: Report generated every 2 minutes")
        print("  - Transaction Processor: every 15 seconds")
        print("  - Daily Reporter: every 2 minutes (simulating 5 PM schedule)")
        print()
        print("In production, use: .schedule(at=time(hour=17, minute=0))")
        print("Demo runs for 5 minutes to show multiple report cycles.")
    else:
        print("PRODUCTION MODE: Report generated daily at 5:00 PM")
        print("  - Transaction Processor: every 15 seconds")
        print("  - Daily Reporter: at 5:00 PM every day")

    print("=" * 70)
    print()

    # Start orchestrator
    serve_task = asyncio.create_task(flock.serve())

    try:
        await asyncio.sleep(300)  # 5 minutes
    except KeyboardInterrupt:
        print("\n\nStopping daily reporter...")
    finally:
        serve_task.cancel()
        try:
            await serve_task
        except asyncio.CancelledError:
            pass

    print()
    print("=" * 70)
    print("Daily report demo complete!")
    print("=" * 70)


async def main_dashboard():
    """
    Dashboard mode: Visualize time-based scheduling

    The dashboard will show:
    - transaction_processor publishing transactions frequently
    - daily_reporter running at scheduled time
    - DailyReport artifacts with aggregated statistics
    """
    print("Starting Daily Report Generator with Dashboard...")
    print("Dashboard will be available at: http://localhost:8344")
    print()
    if DEMO_MODE:
        print("DEMO MODE: Reports every 2 minutes")
    else:
        print("PRODUCTION MODE: Reports at 5:00 PM daily")
    print()
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())
