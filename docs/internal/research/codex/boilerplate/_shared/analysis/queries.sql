-- Basic OpenTelemetry queries for Flock research runs

-- Recent traces
SELECT
  trace_id,
  COUNT(*) AS span_count,
  MIN(start_time) AS trace_start,
  (MAX(end_time) - MIN(start_time))/1000000.0 AS total_duration_ms,
  SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) AS error_spans
FROM spans
GROUP BY trace_id
ORDER BY trace_start DESC
LIMIT 10;

-- Agent execution summary
SELECT
  service AS agent,
  COUNT(*) AS runs,
  AVG(duration_ms) AS avg_ms,
  PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_ms
FROM spans
WHERE name = 'Agent.execute'
GROUP BY service
ORDER BY runs DESC;

-- RED metrics by service
SELECT
  service,
  COUNT(*) AS rate,
  SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) AS errors,
  AVG(duration_ms) AS duration_ms
FROM spans
GROUP BY service
ORDER BY rate DESC;
