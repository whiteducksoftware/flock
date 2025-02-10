import asyncio

from flock.core.logging.handlers import live_update_handler, performance_handler
from flock.core.logging.logger import flock_logger


async def demo_logging():
    """Demonstrate various logging features."""
    # Basic logging with different levels
    flock_logger.info("Starting logging demonstration")
    flock_logger.debug("Debug information", details={"version": "1.0.0"})
    flock_logger.warning("This is a warning message")

    # Performance tracking
    with performance_handler.track_time("data_processing"):
        # Show progress tracking
        with live_update_handler.progress_tracker("Processing data") as update_progress:
            for i in range(5):
                await asyncio.sleep(0.5)  # Simulate work
                update_progress((i + 1) * 20)  # Update progress (20%, 40%, etc.)
                flock_logger.info(f"Processing step {i + 1}")
        performance_handler.display_timings()

    # Show status updates with live panels
    with live_update_handler.update_workflow_status(
        "demo-workflow", "Running", {"steps_completed": 3, "current_phase": "data analysis"}
    ):
        await asyncio.sleep(1)  # Simulate work
        flock_logger.info("Analyzing data...")

    # Track performance of another operation
    with performance_handler.track_time("final_processing"):
        # Show activity status
        with live_update_handler.update_activity_status(
            "activity-1", "Final Processing", "In Progress", {"items_processed": 100}
        ):
            await asyncio.sleep(0.5)  # Simulate work
            flock_logger.info("Finalizing results")

    # Display final performance metrics
    flock_logger.success("Demo completed successfully")
    performance_handler.display_timings()


async def main():
    """Run the logging demonstration."""
    try:
        await demo_logging()
    except Exception as e:
        flock_logger.error(f"Demo failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
