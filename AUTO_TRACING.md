# AUTO_TRACING.md

Windows-friendly cheatsheet for enabling auto tracing and mining `.flock/traces.duckdb` without fighting PowerShell quoting. Use it when you only need the commands; the long-form philosophy still lives in `docs/UNIFIED_TRACING.md`.

---

## 1. Enable tracing for the current PowerShell session

```powershell
$env:FLOCK_AUTO_TRACE = 'true'
$env:FLOCK_TRACE_FILE = 'true'
```

These flags ensure every run writes spans into `.flock/traces.duckdb`. Repeat them inside new terminals (or add them to `.env`).

---

## 2. Verify traces exist

```powershell
Get-ChildItem .flock\traces.duckdb
```

If the file is missing, tracing was off—re-run the script you care about after setting the env vars.

---

## 3. List the most recent traces (PowerShell-safe `uv run`)

```powershell
uv run python -c "import duckdb`nconn=duckdb.connect('.flock/traces.duckdb', read_only=True)`nrows=conn.execute('SELECT trace_id, MIN(start_time) AS started_at_ns, COUNT(*) AS spans FROM spans GROUP BY trace_id ORDER BY started_at_ns DESC LIMIT 5').fetchall()`nfor trace_id, started_ns, span_count in rows:`n    print(trace_id, started_ns, span_count)`nconn.close()"
```

Why the backticks? PowerShell treats `` `n`` as a newline, giving you readable Python inside the string. Avoid single quotes around the command—PowerShell would disable the `` `n`` substitution.

---

## 4. Inspect the latest `Agent.execute` output (e.g., pizza ingredients)

```powershell
uv run python -c "import duckdb, json`nconn=duckdb.connect('.flock/traces.duckdb', read_only=True)`ntrace_id, = conn.execute(\"SELECT trace_id FROM spans WHERE name = 'Agent.execute' ORDER BY start_time DESC LIMIT 1\").fetchone()`nrow = conn.execute(\"SELECT attributes FROM spans WHERE trace_id = ? AND name = 'Agent.execute' ORDER BY start_time DESC LIMIT 1\", [trace_id]).fetchone()`ndata = json.loads(row[0])`nartifacts = json.loads(data['output.value'])`npayload = artifacts[0]['payload']`nprint('Trace:', trace_id)`nprint('Ingredients:')`nfor item in payload.get('ingredients', []):`n    print(' -', item)`nconn.close()"
```

This mirrors the manual inspection from the last debugging session and works out of the box on Windows terminals.

---

## 5. Keep helper scripts handy (optional)

For longer queries, drop a temporary script into `.tmp`:

```powershell
New-Item -ItemType Directory -Force -Path .tmp | Out-Null
$code = @'
import duckdb
import json

conn = duckdb.connect(".flock/traces.duckdb", read_only=True)
query = """
    SELECT trace_id, name, attributes
    FROM spans
    WHERE name IN ('Agent.execute', 'Flock.publish')
    ORDER BY start_time DESC
    LIMIT 10
"""
for trace_id, name, attrs_json in conn.execute(query).fetchall():
    attrs = json.loads(attrs_json)
    print(trace_id, name, attrs.get("output.type"))
conn.close()
'@
Set-Content .tmp\trace_query.py $code
uv run python .tmp\trace_query.py
Remove-Item .tmp\trace_query.py
```

This approach avoids quoting entirely and keeps the workspace clean.

---

## 6. Clean up stale traces

```powershell
uv run python -c "from flock import Flock`nprint(Flock.clear_traces())"
```

The output shows how many spans were deleted. Run this before collecting a fresh trace set so queries stay fast.

---

## 7. Cross-reference

- Full tracing deep dive: `docs/UNIFIED_TRACING.md`
- Observability dashboard tips: `docs/guides/dashboard.md`
- Need to debug without touching PowerShell? Launch the same scripts in Git Bash or WSL—the SQL snippets above translate directly.

Happy tracing!
