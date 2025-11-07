"""
Timer Scheduling: Daily Report Generator

Demonstrates time-based scheduling — a reporter runs at a scheduled time to
summarize transactions produced during the day.

Key concepts
- schedule(at=time(...)) for daily execution (or interval in demo mode)
- Reporter reads context (transactions) and publishes a DailyReport
- Use consumes(..., mode="direct") so the reporter is only triggered by its
  timer, not by every Transaction event
"""

import asyncio
from datetime import date, datetime, time, timedelta

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type


# Configuration
USE_DASHBOARD = False


# Types
@flock_type
class Transaction(BaseModel):
    transaction_id: str = Field(description="Unique transaction identifier")
    amount: float = Field(description="Transaction amount in dollars")
    user_id: str = Field(description="User who made the transaction")
    category: str = Field(description="Transaction category (food, travel, etc)")
    timestamp: datetime = Field(description="When the transaction occurred")
    status: str = Field(description="Transaction status (pending, completed, failed)")


@flock_type
class DailyReport(BaseModel):
    report_date: date = Field(description="Date this report covers")
    total_transactions: int = Field(description="Total number of transactions")
    total_revenue: float = Field(description="Total revenue in dollars")
    avg_transaction: float = Field(description="Average transaction amount")
    completed_count: int = Field(description="Number of completed transactions")
    failed_count: int = Field(description="Number of failed transactions")
    top_category: str = Field(description="Category with most transactions")
    summary: str = Field(description="AI-generated daily summary")
    generated_at: datetime = Field(description="When report was generated")


# Agents
flock = Flock()

# Producer: runs frequently to simulate transactions
transaction_processor = (
    flock.agent("transaction_processor")
    .description(
        "Simulate recent user transactions. Generate realistic records with "
        "amounts, categories, timestamps and completion status."
    )
    .schedule(every=timedelta(seconds=15))
    .publishes(Transaction)
)

# Reporter: daily at 17:00 (demo uses 2-minute interval)
DEMO_MODE = True
if DEMO_MODE:
    daily_reporter = (
        flock.agent("daily_reporter")
        .description(
            "Create an end-of-day financial report. Use the available Transaction "
            "artifacts in context to compute totals, counts, averages and the top "
            "category. Provide a concise, executive-friendly summary."
        )
        .schedule(every=timedelta(minutes=2))
        .consumes(Transaction, mode="direct")
        .publishes(DailyReport)
    )
else:
    daily_reporter = (
        flock.agent("daily_reporter")
        .description(
            "At 5 PM local time, generate an end-of-day financial report from "
            "Transaction artifacts with totals, averages, and key insights."
        )
        .schedule(at=time(hour=17, minute=0))
        .consumes(Transaction, mode="direct")
        .publishes(DailyReport)
    )


# Run
async def main_cli() -> None:
    print("=" * 70)
    print("DAILY REPORT GENERATOR – Time-Based Scheduling Demo")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%H:%M:%S')}")
    if DEMO_MODE:
        print("Demo: reporter runs every 2 minutes; producer every 15 seconds.")
    else:
        print("Production: reporter runs daily at 17:00; producer every 15 seconds.")
    print()
    await flock.run_until_idle(timeout=300)  # 5 minutes
    print("\nDemo complete.")


async def main_dashboard() -> None:
    print("Starting Daily Report Generator with dashboard at http://127.0.0.1:8344 …")
    await flock.serve(dashboard=True)


async def main() -> None:
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())

