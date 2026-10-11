/** An agent's runs as `GET /api/agents/{name}/runs` reports them, newest first. */

import { useEffect, useState } from 'react';

export interface AgentRun {
  runId: string;
  correlationId: string | null;
  startedAt: string | null;
  durationMs: number | null;
  status: 'active' | 'completed' | 'error';
  tokens: number | null;
  /** null: a model of the run has no price */
  costUsd: number | null;
  artifacts: number;
  errorType: string | null;
  errorMessage: string | null;
}

interface ApiRun {
  run_id: string;
  correlation_id?: string | null;
  start_time?: string | null;
  duration_ms?: number | null;
  status?: string;
  metrics?: { tokens_used?: number | null; cost_usd?: number | null; artifacts_produced?: number };
  error_message?: string | null;
  error_type?: string | null;
}

const toRun = (run: ApiRun): AgentRun => ({
  runId: run.run_id,
  correlationId: run.correlation_id ?? null,
  startedAt: run.start_time ?? null,
  durationMs: run.duration_ms ?? null,
  status: run.status === 'completed' || run.status === 'error' ? run.status : 'active',
  tokens: run.metrics?.tokens_used ?? null,
  costUsd: run.metrics?.cost_usd ?? null,
  artifacts: run.metrics?.artifacts_produced ?? 0,
  errorType: run.error_type ?? null,
  errorMessage: run.error_message ?? null,
});

/** The agent's runs, read again whenever its status changes (a run starts or ends). */
export function useAgentRuns(agent: string, status?: string): { runs: AgentRun[] | null; error: string | null } {
  const [runs, setRuns] = useState<AgentRun[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    fetch(`/api/agents/${encodeURIComponent(agent)}/runs`)
      .then((response) => {
        if (!response.ok) throw new Error(`The runs could not be read (${response.status})`);
        return response.json();
      })
      .then((data: { runs?: ApiRun[] }) => {
        if (!current) return;
        setRuns((data.runs ?? []).map(toRun));
        setError(null);
      })
      .catch((reason: unknown) => {
        if (current) setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => {
      current = false;
    };
  }, [agent, status]);

  return { runs, error };
}
