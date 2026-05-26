# flock/core/api/service.py
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flock.core.api.endpoints import FlockBatchRequest
    from flock.core.api.run_store import RunStore
    from flock.core.flock import Flock


from flock.core.logging.logging import get_logger

logger = get_logger("flock.api")

class FlockApiService:
    def __init__(self, flock_instance: "Flock", run_store_instance: "RunStore"):
        self.flock = flock_instance
        self.run_store = run_store_instance
    # You would move the _run_flock, _run_batch, _type_convert_inputs methods here
    # from the old FlockAPI class.
    async def _run_flock(
        self, run_id: str, agent_name: str, inputs: dict[str, Any]
    ):
        """Executes a flock workflow run (internal helper)."""
        try:
            if agent_name not in self.flock.agents:
                raise ValueError(f"Starting agent '{agent_name}' not found")

            typed_inputs = self._type_convert_inputs(agent_name, inputs)

            logger.debug(
                f"Executing flock workflow starting with '{agent_name}' (run_id: {run_id})",
                inputs=typed_inputs,
            )
            # Flock.run_async now handles context creation and execution
            result = await self.flock.run_async(
                start_agent=agent_name, input=typed_inputs
            )
            self.run_store.update_run_result(run_id, result)

            final_agent_name = (
                result.get("agent_name", "N/A") if isinstance(result, dict) else "N/A"
            ) # Handle if result is not a dict (e.g. Box)
            logger.info(
                f"Flock workflow completed (run_id: {run_id})",
                final_agent=final_agent_name,
            )
        except Exception as e:
            logger.error(
                f"Error in flock run {run_id} (started with '{agent_name}'): {e!s}",
                exc_info=True,
            )
            self.run_store.update_run_status(run_id, "failed", str(e))
            raise

    async def _run_batch(self, batch_id: str, request: "FlockBatchRequest"):
        """Executes a batch of runs (internal helper)."""
        try:
            if request.agent_name not in self.flock.agents:
                raise ValueError(f"Agent '{request.agent_name}' not found")

            logger.debug(
                f"Executing batch run starting with '{request.agent_name}' (batch_id: {batch_id})",
                batch_size=len(request.batch_inputs)
                if isinstance(request.batch_inputs, list)
                else "CSV/DataFrame",
            )

            # --- Re-integrating the threaded batch execution from Flock.run_batch_async ---
            import asyncio
            import threading
            from concurrent.futures import ThreadPoolExecutor

            def run_batch_sync_in_thread():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    batch_size = (
                        len(request.batch_inputs)
                        if isinstance(request.batch_inputs, list)
                        else 0 # Or attempt to get from DataFrame/CSV load
                    )
                    if batch_size > 0:
                        self.run_store.set_batch_total_items(batch_id, batch_size)

                    class ProgressTracker:
                        def __init__(self, store, b_id, total_size):
                            self.store, self.batch_id, self.total_size = store, b_id, total_size
                            self.current_count, self.partial_results, self._lock = 0, [], threading.Lock()
                        def increment(self, res=None):
                            with self._lock:
                                self.current_count += 1
                                if res is not None: self.partial_results.append(res)
                                try: self.store.update_batch_progress(self.batch_id, self.current_count, self.partial_results)
                                except Exception as e_prog: logger.error(f"Error updating progress: {e_prog}")
                                return self.current_count

                    progress_tracker = ProgressTracker(self.run_store, batch_id, batch_size)

                    async def progress_aware_worker(index, item_inputs):
                        try:
                            # Call Flock's run_async for a single item
                            item_result = await self.flock.run_async(
                                start_agent=request.agent_name,
                                input=item_inputs,
                                box_result=request.box_results,
                            )
                            progress_tracker.increment(item_result)
                            return item_result
                        except Exception as item_err:
                            logger.error(f"Error processing batch item {index}: {item_err}")
                            progress_tracker.increment(item_err if request.return_errors else None)
                            if request.return_errors: return item_err
                            return None

                    batch_inputs_list = request.batch_inputs
                    actual_results_list = []

                    if isinstance(batch_inputs_list, list):
                        tasks = []
                        for i, item_inputs in enumerate(batch_inputs_list):
                            full_inputs = {**(request.static_inputs or {}), **item_inputs}
                            tasks.append(progress_aware_worker(i, full_inputs))

                        if request.parallel and request.max_workers > 1:
                            semaphore = asyncio.Semaphore(request.max_workers)
                            async def bounded_worker(idx, inputs_item):
                                async with semaphore: return await progress_aware_worker(idx, inputs_item)
                            bounded_tasks = [bounded_worker(i, {**(request.static_inputs or {}), **item}) for i, item in enumerate(batch_inputs_list)]
                            actual_results_list = loop.run_until_complete(asyncio.gather(*bounded_tasks, return_exceptions=request.return_errors))
                        else:
                            for i, item_inputs in enumerate(batch_inputs_list):
                                full_inputs = {**(request.static_inputs or {}), **item_inputs}
                                actual_results_list.append(loop.run_until_complete(progress_aware_worker(i, full_inputs)))
                    else: # DataFrame or CSV path - let Flock's batch processor handle this directly
                        # This path relies on self.flock.run_batch_async being able to run within this new event loop.
                        # It might be simpler to always convert DataFrame/CSV to list of dicts before this point.
                        actual_results_list = loop.run_until_complete(
                            self.flock.run_batch_async(
                                start_agent=request.agent_name,
                                batch_inputs=request.batch_inputs, # DataFrame or path
                                input_mapping=request.input_mapping,
                                static_inputs=request.static_inputs,
                                parallel=request.parallel, # Will be re-evaluated by internal BatchProcessor
                                max_workers=request.max_workers,
                                use_temporal=request.use_temporal, # Will be re-evaluated
                                box_results=request.box_results,
                                return_errors=request.return_errors,
                                silent_mode=True, # Internal batch runs silently for API
                                write_to_csv=None # API handles CSV output separately if needed
                            )
                        )
                        # Progress for DataFrame/CSV would need integration into BatchProcessor or this loop
                        if actual_results_list:
                             self.run_store.set_batch_total_items(batch_id, len(actual_results_list))
                             self.run_store.update_batch_progress(batch_id, len(actual_results_list), actual_results_list)


                    self.run_store.update_batch_result(batch_id, actual_results_list)
                    logger.info(f"Batch run completed (batch_id: {batch_id})", num_results=len(actual_results_list))
                    return actual_results_list
                except Exception as thread_err:
                    logger.error(f"Error in batch run thread {batch_id}: {thread_err!s}", exc_info=True)
                    self.run_store.update_batch_status(batch_id, "failed", str(thread_err))
                    return None
                finally:
                    loop.close()
            # --- End of re-integrated threaded batch execution ---

            # Submit the synchronous function to a thread pool from the main event loop
            main_loop = asyncio.get_running_loop()
            with ThreadPoolExecutor(thread_name_prefix="flock-api-batch") as pool:
                await main_loop.run_in_executor(pool, run_batch_sync_in_thread)

        except Exception as e:
            logger.error(
                f"Error setting up batch run {batch_id} (started with '{request.agent_name}'): {e!s}",
                exc_info=True,
            )
            self.run_store.update_batch_status(batch_id, "failed", str(e))
            raise





    def _type_convert_inputs(
        self, agent_name: str, inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """Converts input values (esp. from forms) to expected Python types."""
        typed_inputs = {}
        agent_def = self.flock.agents.get(agent_name)
        if not agent_def or not agent_def.input or not isinstance(agent_def.input, str):
            return inputs # Return original if no spec or spec is not a string

        parsed_fields = self._parse_input_spec(agent_def.input) # Relies on the old UI helper
        field_types = {f["name"]: f["type"] for f in parsed_fields}

        for k, v in inputs.items():
            target_type_str = field_types.get(k)
            if target_type_str:
                if target_type_str.startswith("bool"):
                    typed_inputs[k] = str(v).lower() in ["true", "on", "1", "yes"] if isinstance(v, str) else bool(v)
                elif target_type_str.startswith("int"):
                    try: typed_inputs[k] = int(v)
                    except (ValueError, TypeError): logger.warning(f"Could not convert '{k}' value '{v}' to int for agent '{agent_name}'"); typed_inputs[k] = v
                elif target_type_str.startswith("float"):
                    try: typed_inputs[k] = float(v)
                    except (ValueError, TypeError): logger.warning(f"Could not convert '{k}' value '{v}' to float for agent '{agent_name}'"); typed_inputs[k] = v
                # TODO: Add list/dict parsing (e.g., json.loads) if type_str indicates these,
                # especially if inputs come from HTML forms as strings.
                else: typed_inputs[k] = v
            else:
                typed_inputs[k] = v
        return typed_inputs
