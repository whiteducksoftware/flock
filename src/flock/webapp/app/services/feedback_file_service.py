"""Methods for creating Feedback-File Downloads."""
import csv
import tempfile
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename
from fastapi import Request
from fastapi.responses import FileResponse

from flock.webapp.app.services.sharing_store import SharedLinkStoreInterface


async def create_xlsx_feedback_file_for_agent(
  request: Request,
  store: SharedLinkStoreInterface,
  agent_name: str,
) -> FileResponse:
  """Creates an XLSX-File containing all feedback-entries for a single agent."""
  from flock.core.flock import Flock

  current_flock_instance: Flock | None = getattr(
    request.app.state, "flock_instance", None
  )

  if not current_flock_instance:
    from fastapi import HTTPException

    raise HTTPException(
      status_code=400,
      detail="No Flock loaded to download feedback for"
    )

  all_agent_names = list(current_flock_instance.agents.keys())

  if not all_agent_names:
    from fastapi import HTTPException

    raise HTTPException(
      status_code=400,
      detail="No agents found in the current Flock"
    )

  all_records = await store.get_all_feedback_records_for_agent(
    agent_name=agent_name
  )

  temp_dir = tempfile.gettempdir()
  timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
  safe_agent_name = secure_filename(agent_name)
  xlsx_filename = f"flock_feedback_{safe_agent_name}_{timestamp}.xlsx"
  xlsx_path = Path(temp_dir) / xlsx_filename
  headers = [
      "feedback_id",
      "share_id",
      "context_type",
      "reason",
      "expected_response",
      "actual_response",
      "created_at",
      "flock_name",
      "agent_name",
      "flock_definition",
    ]

  return await _write_xlsx_file(
    records=all_records,
    path=xlsx_path,
    filename=xlsx_filename,
    headers=headers,
  )

async def create_xlsx_feedback_file(
  request: Request,
  store: SharedLinkStoreInterface
) -> FileResponse:
  """Creates an XLSX-File containing all feddback-entries for all agents."""
  from flock.core.flock import Flock

  current_flock_instance: Flock | None = getattr(
    request.app.state, "flock_instance", None
  )

  if not current_flock_instance:
    # If no flock is loaded, return an error response
    from fastapi import HTTPException

    raise HTTPException(
      status_code=400,
      detail="No Flock loaded to download feedback for"
    )

  # Get all agent names from the current flock
  all_agent_names = list(current_flock_instance.agents.keys())

  if not all_agent_names:

    from fastapi import HTTPException

    raise HTTPException(
      status_code=400,
      detail="No agents found in the current Flock"
    )

  all_records = []
  for agent_name in all_agent_names:
    agent_records = await store.get_all_feedback_records_for_agent(
      agent_name=agent_name,
    )
    all_records.extend(agent_records)

  temp_dir = tempfile.gettempdir()
  timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
  xlsx_filename = f"flock_feedback_all_agents_{timestamp}.xlsx"
  xlsx_path = Path(temp_dir) / xlsx_filename
  headers = [
      "feedback_id",
      "share_id",
      "context_type",
      "reason",
      "expected_response",
      "actual_response",
      "created_at",
      "flock_name",
      "agent_name",
      "flock_definition",
    ]

  return await _write_xlsx_file(
    records=all_records,
    path=xlsx_path,
    filename=xlsx_filename,
    headers=headers,
  )


async def create_csv_feedback_file_for_agent(
  request: Request,
  store: SharedLinkStoreInterface,
  agent_name: str,
  separator: str = ",",
) -> FileResponse:
  """Creates a CSV-File filled with the feedback-records for a single agent."""
  from flock.core.flock import Flock

  current_flock_instance: Flock | None = getattr(
    request.app.state, "flock_instance", None
  )

  if not current_flock_instance:
    # If no flock is loaded, return an error response
    from fastapi import HTTPException

    raise HTTPException(
      status_code=400,
      detail="No Flock loaded to download feedback for"
    )


  # Get all agent names from the current flock
  all_agent_names = list(current_flock_instance.agents.keys())


  if not all_agent_names:

    from fastapi import HTTPException

    raise HTTPException(
      status_code=400,
      detail="No agents found in the current Flock"
    )

  all_records = await store.get_all_feedback_records_for_agent(
    agent_name=agent_name
  )
  temp_dir = tempfile.gettempdir()
  timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
  safe_agent_name = secure_filename(agent_name)
  csv_filename = f"flock_feedback_{safe_agent_name}_{timestamp}.csv"
  csv_path = Path(temp_dir) / csv_filename
  headers = [
    "feedback_id",
    "share_id",
    "context_type",
    "reason",
    "expected_response",
    "actual_response",
    "created_at",
    "flock_name",
    "agent_name",
    "flock_definition",
  ]
  return await _write_csv_file(
    records=all_records,
    path=csv_path,
    headers=headers,
    separator=separator,
    filename=csv_filename,
  )


async def create_csv_feedback_file(
  request: Request,
  store: SharedLinkStoreInterface,
  separator: str = ",",

  ) -> FileResponse:
  """Creates a CSV-File filled with the feedback-records for all agents."""
  from flock.core.flock import Flock

  current_flock_instance: Flock | None = getattr(
    request.app.state, "flock_instance", None
  )

  if not current_flock_instance:
    # If no flock is loaded, return an error response
    from fastapi import HTTPException

    raise HTTPException(
      status_code=400,
      detail="No Flock loaded to download feedback for"
    )

  # Get all agent names from the current flock
  all_agent_names = list(current_flock_instance.agents.keys())

  if not all_agent_names:

    from fastapi import HTTPException

    raise HTTPException(
      status_code=400,
      detail="No agents found in the current Flock"
    )

  all_records = []
  for agent_name in all_agent_names:
    records_for_agent = await store.get_all_feedback_records_for_agent(
      agent_name=agent_name
    )
    all_records.extend(records_for_agent)

  temp_dir = tempfile.gettempdir()
  timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
  csv_filename = f"flock_feedback_all_agents_{timestamp}.csv"
  csv_path = Path(temp_dir) / csv_filename
  headers = [
    "feedback_id",
    "share_id",
    "context_type",
    "reason",
    "expected_response",
    "actual_response",
    "created_at",
    "flock_name",
    "agent_name",
    "flock_definition",
  ]

  return await _write_csv_file(
    records=all_records,
    path=csv_path,
    headers=headers,
    filename=csv_filename,
    separator=separator,
  )

async def _write_xlsx_file(
  records: list[dict],
  headers: list,
  path: str | Path,
  filename: str,
) -> FileResponse:
  """Writes an xlsx-file with the specified records."""
  try:
    import pandas as pd

    # Convert records to a format suitable for
    # pandas DataFrame
    data_rows = []
    for record in records:
      row_data = {}
      for header in headers:
        value = getattr(record, header, None)
        # Convert datetime to string for excel
        if header == "created_at" and value:
          row_data[header] = (
            value.isoformat()
            if isinstance(value, datetime)
            else str(value)
          )
        else:
          row_data[header] = str(value) if value is not None else ""
      data_rows.append(row_data)

    # Create DataFrame and write to Excel
    df = pd.DataFrame(data_rows)
    df.to_excel(str(path), index=False)

    return FileResponse(
      path=str(path),
      filename=filename,
      media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      headers={
        "Content-Disposition": f"attachment; filename={filename}"
      }
    )

  except Exception:
    from fastapi import HTTPException

    raise HTTPException(
      status_code=500,
      detail="Unable to create feedback Excel file"
    )

async def _write_csv_file(
  records: list[dict],
  path: str | Path,
  filename: str,
  headers: list,
  separator: str = ","
) -> FileResponse:
  """Writes a CSV_File with the specified records."""
  try:
    with open(path, "w", newline="", encoding="utf-8") as csvfile:
      writer = csv.DictWriter(
        csvfile,
        fieldnames=headers,
        delimiter=separator
      )
      writer.writeheader()
      for record in records:
        # Convert the Pydantic model
        # to dict and ensure all fields are present
        row_data = {}
        for header in headers:
          value = getattr(record, header, None)
          # Convert datetime to ISO string for CSV
          if header == "created_at" and value:
            row_data[header] = (
              value.isoformat()
              if isinstance(value, datetime)
              else str(value)
            )
          else:
            row_data[header] = str(value) if value is not None else ""
        writer.writerow(row_data)

    return FileResponse(
      path=str(path),
      filename=filename,
      media_type="text/csv",
      headers={
        "Content-Disposition": f"attachment; filename={filename}"
      }
    )
  except Exception:
    from fastapi import HTTPException

    raise HTTPException(
        status_code=500,
        detail="Unable to create feedback-file"
      )
