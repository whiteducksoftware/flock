"""Execute a Flock instance with a selected agent.

This module provides functionality to execute a Flock instance with
a selected agent and input configuration, including batch processing.
"""

import json
import os

import questionary
from rich.console import Console
from rich.panel import Panel

from flock.core.flock import Flock
from flock.core.logging.logging import configure_logging
from flock.core.util.cli_helper import init_console

# Create console instance
console = Console()

# Try importing pandas for DataFrame support
try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    pd = None
    PANDAS_AVAILABLE = False


def execute_flock(flock: Flock):
    """Execute a Flock instance.

    Args:
        flock: The Flock instance to execute
    """
    if not flock:
        console.print("[bold red]Error: No Flock instance provided.[/]")
        return

    agent_names = list(flock._agents.keys())

    if not agent_names:
        console.print("[yellow]No agents in this Flock to execute.[/]")
        return

    init_console()
    console.print(Panel("[bold green]Execute Flock[/]"), justify="center")

    # Step 1: Select start agent
    console.print("\n[bold]Step 1: Select Start Agent[/]")

    start_agent_name = questionary.select(
        "Select an agent to start with:",
        choices=agent_names,
    ).ask()

    if not start_agent_name:
        return

    start_agent = flock._agents[start_agent_name]

    # Step 2: Configure input
    console.print("\n[bold]Step 2: Configure Input[/]")

    # Parse input schema
    input_fields = _parse_input_schema(start_agent.input)

    # If we couldn't parse any fields, ask for generic input
    if not input_fields:
        raw_input = questionary.text(
            "Enter input (JSON format):",
            default="{}",
        ).ask()

        try:
            input_data = json.loads(raw_input)
        except json.JSONDecodeError:
            console.print("[bold red]Error: Invalid JSON input.[/]")
            return
    else:
        # Otherwise, ask for each field
        input_data = {}

        for field, info in input_fields.items():
            field_type = info.get("type", "str")
            description = info.get("description", "")
            prompt = f"Enter value for '{field}'"

            if description:
                prompt += f" ({description})"

            prompt += ":"

            value = questionary.text(prompt).ask()

            # Convert value to appropriate type
            if field_type == "int":
                try:
                    value = int(value)
                except ValueError:
                    console.print(
                        f"[yellow]Warning: Could not convert value to int, using as string.[/]"
                    )

            input_data[field] = value

    # Step 3: Run Options
    console.print("\n[bold]Step 3: Run Options[/]")

    # Logging options
    enable_logging = questionary.confirm(
        "Enable logging?",
        default=False,
    ).ask()
    if enable_logging:
        log_level = questionary.select(
            "Minimum log level:",
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            default="ERROR",
        ).ask()
        configure_logging(flock_level=log_level, external_level=log_level)

    # Preview input
    console.print("\n[bold]Input Preview:[/]")
    console.print(json.dumps(input_data, indent=2))

    # Confirm execution
    confirm = questionary.confirm(
        "Execute Flock with this configuration?",
        default=True,
    ).ask()

    if not confirm:
        return

    # Execute the Flock
    console.print("\n[bold]Executing Flock...[/]")

    try:
        # Logging was configured earlier if enabled

        # Run the Flock
        result = flock.run(
            start_agent=start_agent_name,
            input=input_data,
        )

        # Display result
        console.print("\n[bold green]Execution Complete![/]")

        if result and enable_logging:
            console.print("\n[bold]Result:[/]")
            if isinstance(result, dict):
                # Display as formatted JSON
                console.print(json.dumps(result, indent=2))
            else:
                # Display as plain text
                console.print(str(result))

    except Exception as e:
        console.print(f"\n[bold red]Error during execution:[/] {e!s}")


def _parse_input_schema(input_schema: str) -> dict[str, dict[str, str]]:
    """Parse the input schema string into a field dictionary.

    Args:
        input_schema: The input schema string (e.g., "query: str | The search query")

    Returns:
        A dictionary mapping field names to field info (type, description)
    """
    if not input_schema:
        return {}

    fields = {}

    try:
        # Split by comma for multiple fields
        for field_def in input_schema.split(","):
            field_def = field_def.strip()

            # Check for type hint with colon
            if ":" in field_def:
                field_name, rest = field_def.split(":", 1)
                field_name = field_name.strip()
                rest = rest.strip()

                # Check for description with pipe
                if "|" in rest:
                    field_type, description = rest.split("|", 1)
                    fields[field_name] = {
                        "type": field_type.strip(),
                        "description": description.strip(),
                    }
                else:
                    fields[field_name] = {"type": rest.strip()}
            else:
                # Just a field name without type hint
                if "|" in field_def:
                    field_name, description = field_def.split("|", 1)
                    fields[field_name.strip()] = {
                        "description": description.strip()
                    }
                else:
                    fields[field_def.strip()] = {}

    except Exception as e:
        console.print(
            f"[yellow]Warning: Could not parse input schema: {e!s}[/]"
        )
        return {}

    return fields


def execute_flock_batch(flock: Flock):
    """Execute a Flock instance in batch mode.

    Args:
        flock: The Flock instance to execute
    """
    if not flock:
        console.print("[bold red]Error: No Flock instance provided.[/]")
        return

    agent_names = list(flock._agents.keys())

    if not agent_names:
        console.print("[yellow]No agents in this Flock to execute.[/]")
        return

    init_console()
    console.print(
        Panel("[bold green]Execute Flock - Batch Mode[/]"), justify="center"
    )

    # Step 1: Select start agent
    console.print("\n[bold]Step 1: Select Start Agent[/]")

    start_agent_name = questionary.select(
        "Select an agent to start with:",
        choices=agent_names,
    ).ask()

    if not start_agent_name:
        return

    start_agent = flock._agents[start_agent_name]

    # Step 2: Configure batch input source
    console.print("\n[bold]Step 2: Select Batch Input Source[/]")

    if not PANDAS_AVAILABLE:
        console.print(
            "[yellow]Warning: pandas not available. CSV input/output functionality will be limited.[/]"
        )

    input_source_choices = ["Enter batch items manually"]

    if PANDAS_AVAILABLE:
        input_source_choices.insert(0, "Load from CSV file")

    input_source = questionary.select(
        "How would you like to provide batch inputs?",
        choices=input_source_choices,
    ).ask()

    if not input_source:
        return

    batch_inputs = []
    input_mapping = {}

    if input_source == "Load from CSV file" and PANDAS_AVAILABLE:
        # Ask for CSV file path
        csv_path = questionary.path(
            "Enter path to CSV file:",
        ).ask()

        if not csv_path:
            return

        try:
            # Validate path exists
            if not os.path.exists(csv_path):
                console.print(
                    f"[bold red]Error: File '{csv_path}' does not exist.[/]"
                )
                return

            # Preview CSV
            df = pd.read_csv(csv_path)
            console.print("\n[bold]CSV Preview (first 5 rows):[/]")
            console.print(df.head().to_string())

            # Configure column mapping
            console.print("\n[bold]Configure Column Mapping:[/]")

            # Parse input schema (if available)
            input_fields = _parse_input_schema(start_agent.input)

            # If we have input fields, map CSV columns to them
            if input_fields:
                columns = df.columns.tolist()

                for field in input_fields.keys():
                    field_desc = input_fields[field].get("description", "")
                    prompt = f"Select column for '{field}'"

                    if field_desc:
                        prompt += f" ({field_desc})"

                    selected_col = questionary.select(
                        prompt,
                        choices=["(Skip this field)"] + columns,
                    ).ask()

                    if selected_col and selected_col != "(Skip this field)":
                        input_mapping[selected_col] = field
            else:
                # No schema, ask user to map columns manually
                columns = df.columns.tolist()

                for col in columns:
                    mapping = questionary.text(
                        f"Map column '{col}' to input field (leave empty to ignore):",
                    ).ask()

                    if mapping:
                        input_mapping[col] = mapping

            if not input_mapping:
                console.print("[yellow]Warning: No column mapping defined.[/]")
                if not questionary.confirm(
                    "Continue without mapping?", default=False
                ).ask():
                    return

            # Use the CSV file path directly
            batch_inputs = csv_path

        except Exception as e:
            console.print(f"[bold red]Error loading CSV: {e}[/]")
            return

    elif input_source == "Enter batch items manually":
        # Parse input schema
        input_fields = _parse_input_schema(start_agent.input)

        if not input_fields:
            console.print(
                "[yellow]No input schema available. Using JSON input.[/]"
            )

            while True:
                raw_input = questionary.text(
                    "Enter batch item as JSON (empty to finish):",
                    default="{}",
                ).ask()

                if not raw_input:
                    break

                try:
                    item_data = json.loads(raw_input)
                    batch_inputs.append(item_data)
                    console.print(f"[green]Added item {len(batch_inputs)}[/]")
                except json.JSONDecodeError:
                    console.print("[bold red]Error: Invalid JSON input.[/]")

        else:
            # We have input fields, ask for each field for each item
            item_count = 1

            while True:
                console.print(f"\n[bold]Batch Item {item_count}[/]")

                item_data = {}
                for field, info in input_fields.items():
                    field_type = info.get("type", "str")
                    description = info.get("description", "")
                    prompt = f"Enter value for '{field}'"

                    if description:
                        prompt += f" ({description})"

                    prompt += " (empty to skip):"

                    value = questionary.text(prompt).ask()

                    if not value:
                        continue

                    # Convert value to appropriate type
                    if field_type == "int":
                        try:
                            value = int(value)
                        except ValueError:
                            console.print(
                                f"[yellow]Warning: Could not convert value to int, using as string.[/]"
                            )

                    item_data[field] = value

                if item_data:
                    batch_inputs.append(item_data)
                    console.print(f"[green]Added item {len(batch_inputs)}[/]")

                if not questionary.confirm(
                    "Add another batch item?",
                    default=len(batch_inputs)
                    < 2,  # Default to yes if we have less than 2 items
                ).ask():
                    break

                item_count += 1

    if isinstance(batch_inputs, list) and not batch_inputs:
        console.print("[yellow]No batch items defined. Exiting.[/]")
        return

    # Step 3: Configure static inputs (if needed)
    static_inputs = {}

    if questionary.confirm(
        "Would you like to add static inputs (common to all batch items)?",
        default=False,
    ).ask():
        console.print("\n[bold]Configure Static Inputs[/]")

        raw_static = questionary.text(
            "Enter static inputs as JSON:",
            default="{}",
        ).ask()

        try:
            static_inputs = json.loads(raw_static)
        except json.JSONDecodeError:
            console.print(
                "[bold red]Error: Invalid JSON for static inputs. Proceeding without static inputs.[/]"
            )
            static_inputs = {}

    # Step 4: Configure batch execution options
    console.print("\n[bold]Step 4: Configure Batch Execution Options[/]")

    # Determine if we should use Temporal
    use_temporal = False
    # if questionary.confirm(
    #     f"Override Temporal setting? (Current: {flock.enable_temporal})",
    #     default=False,
    # ).ask():
    #     use_temporal = questionary.confirm(
    #         "Use Temporal for batch execution?",
    #         default=flock.enable_temporal,
    #     ).ask()

    # Configure parallelism
    parallel = True
    max_workers = 5

    if not flock.enable_temporal if use_temporal is None else not use_temporal:
        parallel = questionary.confirm(
            "Run batch items in parallel?",
            default=True,
        ).ask()

        if parallel:
            max_workers_input = questionary.text(
                "Maximum number of parallel workers:",
                default="5",
            ).ask()

            try:
                max_workers = int(max_workers_input)
            except ValueError:
                console.print(
                    "[yellow]Invalid worker count. Using default (5).[/]"
                )
                max_workers = 5

    # Configure output options
    silent_mode = questionary.confirm(
        "Use silent mode with progress bar? (Recommended for large batches)",
        default=True,
    ).ask()

    write_to_csv = None
    if (
        PANDAS_AVAILABLE
        and questionary.confirm(
            "Write results to CSV file?",
            default=True,
        ).ask()
    ):
        write_to_csv = questionary.text(
            "CSV output path:",
            default="batch_results.csv",
        ).ask()

        hide_columns = questionary.text(
            "Hide columns (comma-separated - leave blank for hiding no columns):",
            default="",
        ).ask()

        hide_columns = hide_columns.split(",") if hide_columns else []

        delimiter = questionary.text(
            "Delimiter (default is comma):",
            default=",",
        ).ask()

    # Logging options
    enable_logging = questionary.confirm(
        "Enable logging?",
        default=False,
    ).ask()
    if enable_logging:
        log_level = questionary.select(
            "Minimum log level:",
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            default="ERROR",
        ).ask()
        configure_logging(log_level)

    # Preview configuration
    console.print("\n[bold]Batch Configuration Preview:[/]")
    console.print(f"Agent: {start_agent_name}")

    if isinstance(batch_inputs, str):
        console.print(f"Input Source: CSV file ({batch_inputs})")
        console.print(f"Column Mapping: {input_mapping}")
    else:
        console.print(f"Input Source: Manual entry ({len(batch_inputs)} items)")

    if static_inputs:
        console.print(f"Static Inputs: {json.dumps(static_inputs, indent=2)}")

    # temporal_status = (
    #     "Default" if use_temporal is None else ("Yes" if use_temporal else "No")
    # )
    # console.print(f"Use Temporal: {temporal_status}")

    if not (flock.enable_temporal if use_temporal is None else use_temporal):
        console.print(f"Parallel Execution: {parallel}")
        if parallel:
            console.print(f"Max Workers: {max_workers}")

    console.print(f"Silent Mode: {silent_mode}")

    if write_to_csv:
        console.print(f"Write Results to: {write_to_csv}")

    # Confirm execution
    confirm = questionary.confirm(
        "Execute batch with this configuration?",
        default=True,
    ).ask()

    if not confirm:
        return

    # Execute the batch
    console.print("\n[bold]Executing Batch...[/]")

    try:
        # Logging was already configured above if enabled

        # Run the batch
        results = flock.run_batch(
            start_agent=start_agent_name,
            batch_inputs=batch_inputs,
            input_mapping=input_mapping or None,
            static_inputs=static_inputs or None,
            parallel=parallel,
            max_workers=max_workers,
            use_temporal=use_temporal,
            box_results=True,
            return_errors=True,
            silent_mode=silent_mode,
            write_to_csv=write_to_csv,
            hide_columns=hide_columns,
            delimiter=delimiter,
        )

        # Display results summary
        console.print("\n[bold green]Batch Execution Complete![/]")

        success_count = sum(1 for r in results if not isinstance(r, Exception))
        error_count = sum(1 for r in results if isinstance(r, Exception))

        console.print(f"Total Items: {len(results)}")
        console.print(f"Successful: {success_count}")

        if error_count > 0:
            console.print(f"[bold red]Errors: {error_count}[/]")

        # Ask if user wants to see detailed results
        if questionary.confirm(
            "View detailed results?",
            default=False,
        ).ask():
            for i, result in enumerate(results):
                console.print(f"\n[bold]Item {i + 1}:[/]")
                if isinstance(result, Exception):
                    console.print(f"[bold red]Error: {result}[/]")
                else:
                    # Display as formatted JSON
                    try:
                        console.print(json.dumps(result, indent=2))
                    except:
                        console.print(str(result))

        if write_to_csv:
            console.print(f"\n[green]Results written to: {write_to_csv}[/]")

    except Exception as e:
        console.print(f"\n[bold red]Error during batch execution:[/] {e!s}")
