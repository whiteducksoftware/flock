# src/flock/core/scheduler.py (new file or inside flock.py)
import asyncio
import traceback
from datetime import datetime, timedelta, timezone

from croniter import croniter  # pip install croniter

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent  # For type hinting
from flock.core.logging.logging import get_logger

logger = get_logger("flock.scheduler")

class FlockScheduler:
    def __init__(self, flock_instance: Flock):
        self.flock = flock_instance
        self._scheduled_tasks: list[tuple[FlockAgent, croniter | timedelta, datetime | None]] = []
        self._stop_event = asyncio.Event()
        self._is_running = False

    def _parse_schedule_expression(self, expression: str) -> croniter | timedelta:
        """Parses a schedule expression.
        Supports cron syntax and simple intervals like 'every Xm', 'every Xh', 'every Xd'.
        """
        expression = expression.strip().lower()
        if expression.startswith("every "):
            try:
                parts = expression.split(" ")
                value = int(parts[1][:-1])
                unit = parts[1][-1]
                if unit == 's': return timedelta(seconds=value)
                if unit == 'm': return timedelta(minutes=value)
                elif unit == 'h': return timedelta(hours=value)
                elif unit == 'd': return timedelta(days=value)
                else: raise ValueError(f"Invalid time unit: {unit}")
            except Exception as e:
                logger.error(f"Invalid interval expression '{expression}': {e}")
                raise ValueError(f"Invalid interval expression: {expression}") from e
        else:
            # Assume cron expression
            if not croniter.is_valid(expression):
                raise ValueError(f"Invalid cron expression: {expression}")
            return croniter(expression, datetime.now(timezone.utc))

    def add_agent(self, agent: FlockAgent):
        """Adds an agent to the scheduler if it has a schedule expression."""
        # Assuming schedule_expression is stored in agent._flock_config or a dedicated field
        schedule_expression = None
        if hasattr(agent, '_flock_config') and isinstance(agent._flock_config, dict):
            schedule_expression = agent._flock_config.get('schedule_expression')
        elif hasattr(agent, 'schedule_expression'): # If directly on agent
             schedule_expression = agent.schedule_expression
        elif hasattr(agent, 'config') and hasattr(agent.config, 'schedule_expression'): # If on agent.config
            schedule_expression = agent.config.schedule_expression


        if not schedule_expression:
            logger.warning(f"Agent '{agent.name}' has no schedule_expression. Skipping.")
            return

        try:
            parsed_schedule = self._parse_schedule_expression(schedule_expression)
            self._scheduled_tasks.append((agent, parsed_schedule, None)) # agent, schedule, last_run_utc
            logger.info(f"Scheduled agent '{agent.name}' with expression: {schedule_expression}")
        except ValueError as e:
            logger.error(f"Could not schedule agent '{agent.name}': {e}")

    def _load_scheduled_agents_from_flock(self):
        """Scans the Flock instance for agents with scheduling configuration."""
        self._scheduled_tasks = [] # Clear existing before loading
        for agent_name, agent_instance in self.flock.agents.items():
            self.add_agent(agent_instance)
        logger.info(f"Loaded {len(self._scheduled_tasks)} scheduled agents from Flock '{self.flock.name}'.")

    async def _run_agent_task(self, agent: FlockAgent, trigger_time: datetime):
        logger.info(f"Triggering scheduled agent '{agent.name}' at {trigger_time.isoformat()}")
        try:
            # Input for a scheduled agent could include the trigger time
            await self.flock.run_async(start_agent=agent.name, input={"trigger_time": trigger_time})
            logger.info(f"Scheduled agent '{agent.name}' finished successfully.")
        except Exception as e:
            logger.error(f"Error running scheduled agent '{agent.name}': {e}\n{traceback.format_exc()}")

    async def _scheduler_loop(self):
        self._is_running = True
        logger.info("FlockScheduler loop started.")
        while not self._stop_event.is_set():
            now_utc = datetime.now(timezone.utc)
            tasks_to_run_this_cycle = []

            for i, (agent, schedule, last_run_utc) in enumerate(self._scheduled_tasks):
                should_run = False
                next_run_utc = None

                if isinstance(schedule, croniter):
                    # For cron, get the next scheduled time AFTER the last run (or now if never run)
                    base_time = last_run_utc if last_run_utc else now_utc
                    # Croniter's get_next gives the next time *after* the base_time.
                    # If last_run_utc is None (first run), we check if the *current* now_utc
                    # is past the first scheduled time.
                    # A simpler check: is `now_utc` >= `schedule.get_next(datetime, base_time=last_run_utc if last_run_utc else now_utc - timedelta(seconds=1))` ?
                    # Let's refine croniter check to be more precise.
                    # If we are past the *next* scheduled time since *last check*
                    if last_run_utc is None: # First run check
                        next_run_utc = schedule.get_next(datetime, start_time=now_utc - timedelta(seconds=1)) # Check if first run is due
                        if next_run_utc <= now_utc:
                            should_run = True
                    else:
                        next_run_utc = schedule.get_next(datetime, start_time=last_run_utc)
                        if next_run_utc <= now_utc:
                            should_run = True

                elif isinstance(schedule, timedelta): # Simple interval
                    if last_run_utc is None or (now_utc - last_run_utc >= schedule):
                        should_run = True
                        next_run_utc = now_utc # Or now_utc + schedule for next interval start
                    else:
                        next_run_utc = last_run_utc + schedule


                if should_run:
                    tasks_to_run_this_cycle.append(self._run_agent_task(agent, now_utc))
                    # Update last_run_utc for this agent *before* awaiting its execution
                    # For cron, advance the iterator to the *current* scheduled time that triggered it.
                    if isinstance(schedule, croniter):
                         current_cron_trigger = schedule.get_current(datetime) # This is the time it *should* have run
                         self._scheduled_tasks[i] = (agent, schedule, current_cron_trigger)

                    elif isinstance(schedule, timedelta):
                        self._scheduled_tasks[i] = (agent, schedule, now_utc) # Mark as run now

            if tasks_to_run_this_cycle:
                await asyncio.gather(*tasks_to_run_this_cycle, return_exceptions=True)

            try:
                # Sleep for a short interval, e.g., 10 seconds, or until stop_event is set
                await asyncio.wait_for(self._stop_event.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                pass # Timeout is normal, means continue loop
        self._is_running = False
        logger.info("FlockScheduler loop stopped.")

    async def start(self) -> asyncio.Task | None: # Modified to return Task or None
        if self._is_running:
            logger.warning("Scheduler is already running.")
            return None # Or return the existing task if you store it

        self._load_scheduled_agents_from_flock()
        if not self._scheduled_tasks:
            logger.info("No scheduled agents found. Scheduler will not start a loop task.")
            return None # Return None if no tasks to schedule

        self._stop_event.clear()
        loop_task = asyncio.create_task(self._scheduler_loop())
        # Store the task if you need to reference it, e.g., for forced cancellation beyond _stop_event
        # self._loop_task = loop_task
        return loop_task # Return the created task

    async def stop(self):
        if not self._is_running and not self._stop_event.is_set(): # Check if stop already called
            logger.info("Scheduler is not running or already signaled to stop.")
            return
        logger.info("Stopping FlockScheduler...")
        self._stop_event.set()
        # If you stored self._loop_task, you can await it here or in the lifespan manager
        # await self._loop_task # (This might block if loop doesn't exit quickly)
