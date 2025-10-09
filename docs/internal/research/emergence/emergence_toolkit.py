"""
Emergent Behavior Analysis Toolkit for Flock

This toolkit provides analysis functions for studying emergent coordination
phenomena in blackboard-based multi-agent systems.

Usage:
    analyzer = EmergenceAnalyzer(".flock/traces.duckdb")
    report = analyzer.generate_comprehensive_report()
    print(report)
"""

import duckdb
import pandas as pd
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path
import json


@dataclass
class CascadePattern:
    """Represents a discovered cascade pattern"""
    path: List[str]
    frequency: int
    avg_duration_ms: float
    success_rate: float


@dataclass
class ParallelBurst:
    """Represents parallel agent execution"""
    trace_id: str
    concurrent_agents: int
    sequential_time_ms: float
    parallel_time_ms: float
    speedup: float


@dataclass
class FeedbackLoop:
    """Represents an iterative refinement pattern"""
    agent_name: str
    iterations: int
    converged: bool
    final_quality: Optional[float]


class EmergenceAnalyzer:
    """Toolkit for analyzing emergent phenomena in Flock traces"""

    def __init__(self, db_path: str = ".flock/traces.duckdb"):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Trace database not found: {db_path}")
        self.conn = duckdb.connect(str(self.db_path))

    # ========================================================================
    # 1. CASCADE PATTERN ANALYSIS
    # ========================================================================

    def measure_cascade_depth(self) -> pd.DataFrame:
        """Measure cascade depth distribution across all traces"""

        query = """
        WITH RECURSIVE cascade AS (
            -- Start with root spans
            SELECT
                trace_id,
                span_id,
                parent_id,
                name,
                service,
                duration_ms,
                1 as depth,
                ARRAY[name] as path
            FROM spans
            WHERE parent_id IS NULL

            UNION ALL

            -- Recursively add children
            SELECT
                s.trace_id,
                s.span_id,
                s.parent_id,
                s.name,
                s.service,
                s.duration_ms,
                c.depth + 1,
                array_append(c.path, s.name)
            FROM spans s
            JOIN cascade c ON s.parent_id = c.span_id
        )
        SELECT
            trace_id,
            MAX(depth) as max_depth,
            COUNT(DISTINCT span_id) as total_spans,
            SUM(duration_ms) as total_duration_ms,
            list_distinct(path) as execution_paths
        FROM cascade
        GROUP BY trace_id
        ORDER BY max_depth DESC
        """

        return self.conn.execute(query).df()

    def find_common_cascades(self, min_frequency: int = 2) -> List[CascadePattern]:
        """Extract frequently occurring agent cascade patterns"""

        query = """
        WITH RECURSIVE cascade AS (
            SELECT
                trace_id,
                span_id,
                parent_id,
                name,
                service,
                duration_ms,
                status_code,
                1 as depth,
                name as path_str,
                ARRAY[name] as path_arr
            FROM spans
            WHERE parent_id IS NULL AND service = 'agent'

            UNION ALL

            SELECT
                s.trace_id,
                s.span_id,
                s.parent_id,
                s.name,
                s.service,
                s.duration_ms,
                s.status_code,
                c.depth + 1,
                c.path_str || ' → ' || s.name,
                array_append(c.path_arr, s.name)
            FROM spans s
            JOIN cascade c ON s.parent_id = c.span_id
            WHERE s.service = 'agent'
        )
        SELECT
            path_str as path,
            path_arr,
            COUNT(*) as frequency,
            AVG(duration_ms) as avg_duration_ms,
            SUM(CASE WHEN status_code = 'OK' THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as success_rate
        FROM cascade
        WHERE depth >= 2  -- At least 2 agents in cascade
        GROUP BY path_str, path_arr
        HAVING COUNT(*) >= ?
        ORDER BY frequency DESC
        """

        result = self.conn.execute(query, [min_frequency]).fetchall()

        patterns = []
        for row in result:
            patterns.append(CascadePattern(
                path=row[1],  # path_arr
                frequency=row[2],
                avg_duration_ms=row[3],
                success_rate=row[4]
            ))

        return patterns

    # ========================================================================
    # 2. PARALLEL EXECUTION ANALYSIS
    # ========================================================================

    def detect_parallel_bursts(self) -> List[ParallelBurst]:
        """Identify traces with significant parallel agent execution"""

        query = """
        WITH agent_spans AS (
            SELECT
                trace_id,
                span_id,
                start_time,
                end_time,
                duration_ms,
                name
            FROM spans
            WHERE service = 'agent'
        ),
        parallel_groups AS (
            SELECT
                a1.trace_id,
                COUNT(DISTINCT a1.span_id) as concurrent_agents,
                SUM(a1.duration_ms) as sequential_time_ms,
                MAX(a1.duration_ms) as parallel_time_ms,
                list(DISTINCT a1.name) as agent_names
            FROM agent_spans a1
            JOIN agent_spans a2 ON
                a1.trace_id = a2.trace_id AND
                a1.span_id != a2.span_id AND
                a1.start_time <= a2.end_time AND
                a1.end_time >= a2.start_time  -- Time overlap
            GROUP BY a1.trace_id
            HAVING concurrent_agents > 1
        )
        SELECT
            trace_id,
            concurrent_agents,
            sequential_time_ms,
            parallel_time_ms,
            sequential_time_ms / NULLIF(parallel_time_ms, 0) as speedup,
            agent_names
        FROM parallel_groups
        ORDER BY speedup DESC
        """

        result = self.conn.execute(query).fetchall()

        bursts = []
        for row in result:
            bursts.append(ParallelBurst(
                trace_id=row[0],
                concurrent_agents=row[1],
                sequential_time_ms=row[2],
                parallel_time_ms=row[3],
                speedup=row[4] if row[4] else 1.0
            ))

        return bursts

    def measure_parallel_efficiency(self) -> Dict[str, float]:
        """Calculate average parallelization efficiency metrics"""

        bursts = self.detect_parallel_bursts()

        if not bursts:
            return {
                'avg_speedup': 1.0,
                'max_speedup': 1.0,
                'avg_concurrency': 1.0,
                'traces_with_parallelism': 0
            }

        return {
            'avg_speedup': sum(b.speedup for b in bursts) / len(bursts),
            'max_speedup': max(b.speedup for b in bursts),
            'avg_concurrency': sum(b.concurrent_agents for b in bursts) / len(bursts),
            'traces_with_parallelism': len(bursts)
        }

    # ========================================================================
    # 3. FILTER EFFECTIVENESS ANALYSIS
    # ========================================================================

    def analyze_filter_effectiveness(self) -> pd.DataFrame:
        """Calculate precision and recall for agent filters"""

        query = """
        WITH agent_activations AS (
            SELECT
                json_extract_string(attributes, '$.agent_name') as agent_name,
                json_extract_string(attributes, '$.artifact_type') as artifact_type,
                json_extract_string(attributes, '$.filter_matched') as filter_matched,
                json_extract_string(attributes, '$.produced_artifacts') as produced_count,
                status_code
            FROM spans
            WHERE service = 'agent'
            AND json_extract_string(attributes, '$.agent_name') IS NOT NULL
        )
        SELECT
            agent_name,
            artifact_type,
            COUNT(*) as total_activations,
            SUM(CASE WHEN CAST(produced_count AS INTEGER) > 0 THEN 1 ELSE 0 END) as productive_activations,
            SUM(CASE WHEN status_code = 'OK' THEN 1 ELSE 0 END) as successful_activations,
            SUM(CASE WHEN CAST(produced_count AS INTEGER) > 0 THEN 1 ELSE 0 END)::FLOAT /
                NULLIF(COUNT(*), 0) as precision
        FROM agent_activations
        GROUP BY agent_name, artifact_type
        ORDER BY total_activations DESC
        """

        return self.conn.execute(query).df()

    # ========================================================================
    # 4. FEEDBACK LOOP DETECTION
    # ========================================================================

    def find_feedback_loops(self) -> List[FeedbackLoop]:
        """Detect iterative refinement patterns (agents consuming own output types)"""

        query = """
        WITH agent_io AS (
            SELECT DISTINCT
                json_extract_string(attributes, '$.agent_name') as agent,
                json_extract_string(attributes, '$.consumed_types') as consumed,
                json_extract_string(attributes, '$.published_types') as published,
                trace_id
            FROM spans
            WHERE service = 'agent'
        ),
        feedback_traces AS (
            SELECT
                agent,
                trace_id,
                consumed,
                published
            FROM agent_io
            WHERE consumed LIKE '%' || published || '%'  -- Consuming same type it produces
        ),
        iteration_counts AS (
            SELECT
                ft.agent,
                ft.trace_id,
                COUNT(s.span_id) as iterations,
                MAX(CAST(json_extract_string(s.attributes, '$.quality_score') AS FLOAT)) as final_quality,
                BOOL_OR(s.status_code = 'ERROR') as has_errors
            FROM feedback_traces ft
            JOIN spans s ON
                ft.trace_id = s.trace_id AND
                json_extract_string(s.attributes, '$.agent_name') = ft.agent
            GROUP BY ft.agent, ft.trace_id
        )
        SELECT
            agent,
            trace_id,
            iterations,
            final_quality,
            NOT has_errors as converged
        FROM iteration_counts
        ORDER BY iterations DESC
        """

        result = self.conn.execute(query).fetchall()

        loops = []
        for row in result:
            loops.append(FeedbackLoop(
                agent_name=row[0],
                iterations=row[2],
                converged=row[4],
                final_quality=row[3]
            ))

        return loops

    # ========================================================================
    # 5. WORKFLOW PATTERN MINING
    # ========================================================================

    def mine_workflow_patterns(self, min_support: float = 0.1) -> List[Dict]:
        """Extract frequent agent execution sequences (workflow patterns)"""

        # Get all agent sequences
        query = """
        WITH RECURSIVE cascade AS (
            SELECT
                trace_id,
                span_id,
                parent_id,
                name,
                1 as position,
                ARRAY[name] as sequence
            FROM spans
            WHERE parent_id IS NULL AND service = 'agent'

            UNION ALL

            SELECT
                s.trace_id,
                s.span_id,
                s.parent_id,
                s.name,
                c.position + 1,
                array_append(c.sequence, s.name)
            FROM spans s
            JOIN cascade c ON s.parent_id = c.span_id
            WHERE s.service = 'agent'
        )
        SELECT
            list_distinct(sequence) as sequences,
            trace_id
        FROM cascade
        GROUP BY trace_id
        """

        df = self.conn.execute(query).df()

        # Count sequence frequencies
        all_sequences = []
        for sequences in df['sequences']:
            all_sequences.extend(sequences)

        sequence_counts = Counter(tuple(seq) for seq in all_sequences)
        total_traces = len(df)
        min_count = int(total_traces * min_support)

        # Filter by minimum support
        patterns = [
            {
                'pattern': list(seq),
                'count': count,
                'support': count / total_traces,
                'pattern_str': ' → '.join(seq)
            }
            for seq, count in sequence_counts.most_common()
            if count >= min_count
        ]

        return patterns

    # ========================================================================
    # 6. AGENT COUPLING ANALYSIS
    # ========================================================================

    def build_coupling_matrix(self) -> pd.DataFrame:
        """Build matrix showing which agents consume which agents' outputs"""

        query = """
        WITH artifact_flow AS (
            SELECT
                a1.trace_id,
                json_extract_string(a1.attributes, '$.agent_name') as producer,
                json_extract_string(a1.attributes, '$.published_types') as artifact_type,
                json_extract_string(a2.attributes, '$.agent_name') as consumer
            FROM spans a1
            JOIN spans a2 ON
                a1.trace_id = a2.trace_id AND
                a1.end_time <= a2.start_time AND  -- Producer finishes before consumer starts
                json_extract_string(a2.attributes, '$.consumed_types') LIKE
                    '%' || json_extract_string(a1.attributes, '$.published_types') || '%'
            WHERE
                a1.service = 'agent' AND
                a2.service = 'agent' AND
                a1.span_id != a2.span_id
        )
        SELECT
            producer,
            consumer,
            artifact_type,
            COUNT(*) as coupling_strength
        FROM artifact_flow
        WHERE producer IS NOT NULL AND consumer IS NOT NULL
        GROUP BY producer, consumer, artifact_type
        ORDER BY coupling_strength DESC
        """

        return self.conn.execute(query).df()

    def identify_hub_agents(self) -> Dict[str, List[str]]:
        """Identify central agents (many consumers) vs leaf agents (few consumers)"""

        coupling = self.build_coupling_matrix()

        # Producers with many consumers = hubs
        producer_counts = coupling.groupby('producer')['consumer'].nunique().sort_values(ascending=False)

        # Consumers with many producers = aggregators
        consumer_counts = coupling.groupby('consumer')['producer'].nunique().sort_values(ascending=False)

        return {
            'hub_agents': producer_counts.head(5).to_dict(),
            'aggregator_agents': consumer_counts.head(5).to_dict(),
            'isolated_agents': self._find_isolated_agents(coupling)
        }

    def _find_isolated_agents(self, coupling_df: pd.DataFrame) -> List[str]:
        """Find agents with no coupling (neither produce for others nor consume from others)"""

        all_agents_query = """
        SELECT DISTINCT json_extract_string(attributes, '$.agent_name') as agent
        FROM spans
        WHERE service = 'agent' AND json_extract_string(attributes, '$.agent_name') IS NOT NULL
        """

        all_agents = set(self.conn.execute(all_agents_query).df()['agent'])
        coupled_agents = set(coupling_df['producer']) | set(coupling_df['consumer'])

        return list(all_agents - coupled_agents)

    # ========================================================================
    # 7. EMERGENCE METRICS
    # ========================================================================

    def calculate_emergence_score(self) -> Dict[str, float]:
        """Calculate overall emergence score based on multiple factors"""

        # Factor 1: Cascade complexity
        cascades = self.measure_cascade_depth()
        cascade_score = cascades['max_depth'].mean() if not cascades.empty else 0

        # Factor 2: Parallelization efficiency
        parallel = self.measure_parallel_efficiency()
        parallel_score = parallel['avg_speedup']

        # Factor 3: Filter sophistication
        filters = self.analyze_filter_effectiveness()
        filter_score = filters['precision'].mean() if not filters.empty else 0

        # Factor 4: Feedback loop presence
        loops = self.find_feedback_loops()
        loop_score = len(loops) / 10.0  # Normalize to 0-1 range

        # Combined score (weighted average)
        weights = {'cascade': 0.3, 'parallel': 0.3, 'filter': 0.2, 'loop': 0.2}

        total_score = (
            cascade_score * weights['cascade'] +
            parallel_score * weights['parallel'] +
            filter_score * weights['filter'] +
            loop_score * weights['loop']
        )

        return {
            'total_emergence_score': total_score,
            'cascade_complexity': cascade_score,
            'parallel_efficiency': parallel_score,
            'filter_sophistication': filter_score,
            'feedback_presence': loop_score
        }

    # ========================================================================
    # 8. COMPREHENSIVE REPORTING
    # ========================================================================

    def generate_comprehensive_report(self) -> str:
        """Generate full emergence analysis report"""

        report_lines = [
            "=" * 80,
            "EMERGENT BEHAVIOR ANALYSIS REPORT",
            "=" * 80,
            "",
            "Database: " + str(self.db_path),
            "",
        ]

        # 1. Overall Metrics
        report_lines.append("1. EMERGENCE METRICS")
        report_lines.append("-" * 40)
        metrics = self.calculate_emergence_score()
        for key, value in metrics.items():
            report_lines.append(f"  {key}: {value:.3f}")
        report_lines.append("")

        # 2. Cascade Patterns
        report_lines.append("2. CASCADE PATTERNS")
        report_lines.append("-" * 40)
        cascades = self.measure_cascade_depth()
        if not cascades.empty:
            report_lines.append(f"  Total traces: {len(cascades)}")
            report_lines.append(f"  Average cascade depth: {cascades['max_depth'].mean():.1f}")
            report_lines.append(f"  Max cascade depth: {cascades['max_depth'].max()}")
            report_lines.append(f"  Average duration: {cascades['total_duration_ms'].mean():.0f} ms")

            # Common patterns
            patterns = self.find_common_cascades(min_frequency=2)
            if patterns:
                report_lines.append("")
                report_lines.append("  Most frequent cascades:")
                for i, pattern in enumerate(patterns[:5], 1):
                    report_lines.append(f"    {i}. {' → '.join(pattern.path)}")
                    report_lines.append(f"       Frequency: {pattern.frequency}, Success: {pattern.success_rate:.1%}")
        report_lines.append("")

        # 3. Parallel Execution
        report_lines.append("3. PARALLEL EXECUTION")
        report_lines.append("-" * 40)
        parallel_stats = self.measure_parallel_efficiency()
        for key, value in parallel_stats.items():
            report_lines.append(f"  {key}: {value:.2f}")
        report_lines.append("")

        # 4. Feedback Loops
        report_lines.append("4. FEEDBACK LOOPS")
        report_lines.append("-" * 40)
        loops = self.find_feedback_loops()
        report_lines.append(f"  Total feedback loops detected: {len(loops)}")
        if loops:
            converged = sum(1 for l in loops if l.converged)
            report_lines.append(f"  Converged: {converged}/{len(loops)} ({converged/len(loops):.1%})")
            report_lines.append(f"  Average iterations: {sum(l.iterations for l in loops)/len(loops):.1f}")

            # Top loops by iterations
            report_lines.append("")
            report_lines.append("  Most iterative loops:")
            for i, loop in enumerate(sorted(loops, key=lambda l: l.iterations, reverse=True)[:5], 1):
                quality_str = f", Quality: {loop.final_quality:.2f}" if loop.final_quality else ""
                report_lines.append(f"    {i}. {loop.agent_name}: {loop.iterations} iterations{quality_str}")
        report_lines.append("")

        # 5. Agent Coupling
        report_lines.append("5. AGENT COUPLING")
        report_lines.append("-" * 40)
        hubs = self.identify_hub_agents()
        report_lines.append("  Hub agents (most consumers):")
        for agent, count in list(hubs['hub_agents'].items())[:3]:
            report_lines.append(f"    - {agent}: {count} consumers")

        report_lines.append("")
        report_lines.append("  Aggregator agents (most producers):")
        for agent, count in list(hubs['aggregator_agents'].items())[:3]:
            report_lines.append(f"    - {agent}: {count} producers")

        if hubs['isolated_agents']:
            report_lines.append("")
            report_lines.append(f"  Isolated agents: {', '.join(hubs['isolated_agents'])}")
        report_lines.append("")

        # 6. Workflow Patterns
        report_lines.append("6. WORKFLOW PATTERNS")
        report_lines.append("-" * 40)
        patterns = self.mine_workflow_patterns(min_support=0.1)
        report_lines.append(f"  Discovered patterns (min support 10%): {len(patterns)}")
        if patterns:
            report_lines.append("")
            report_lines.append("  Top patterns:")
            for i, pattern in enumerate(patterns[:5], 1):
                report_lines.append(f"    {i}. {pattern['pattern_str']}")
                report_lines.append(f"       Support: {pattern['support']:.1%} ({pattern['count']} occurrences)")
        report_lines.append("")

        report_lines.append("=" * 80)

        return "\n".join(report_lines)

    def export_to_json(self, output_path: str) -> None:
        """Export all analysis results to JSON file"""

        results = {
            'emergence_metrics': self.calculate_emergence_score(),
            'cascade_patterns': [
                {
                    'path': p.path,
                    'frequency': p.frequency,
                    'avg_duration_ms': p.avg_duration_ms,
                    'success_rate': p.success_rate
                }
                for p in self.find_common_cascades()
            ],
            'parallel_efficiency': self.measure_parallel_efficiency(),
            'feedback_loops': [
                {
                    'agent': l.agent_name,
                    'iterations': l.iterations,
                    'converged': l.converged,
                    'final_quality': l.final_quality
                }
                for l in self.find_feedback_loops()
            ],
            'workflow_patterns': self.mine_workflow_patterns(),
            'agent_coupling': {
                'hub_agents': self.identify_hub_agents()['hub_agents'],
                'aggregators': self.identify_hub_agents()['aggregator_agents'],
                'isolated': self.identify_hub_agents()['isolated_agents']
            }
        }

        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"Analysis results exported to {output_path}")


# ============================================================================
# CLI INTERFACE
# ============================================================================

def main():
    """Command-line interface for emergence analysis"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze emergent behavior in Flock execution traces"
    )
    parser.add_argument(
        '--db',
        default='.flock/traces.duckdb',
        help='Path to DuckDB trace database'
    )
    parser.add_argument(
        '--export',
        help='Export results to JSON file'
    )
    parser.add_argument(
        '--format',
        choices=['text', 'json'],
        default='text',
        help='Output format'
    )

    args = parser.parse_args()

    # Run analysis
    analyzer = EmergenceAnalyzer(args.db)

    if args.format == 'text':
        print(analyzer.generate_comprehensive_report())
    else:
        import json
        results = {
            'metrics': analyzer.calculate_emergence_score(),
            'cascades': len(analyzer.find_common_cascades()),
            'parallel_efficiency': analyzer.measure_parallel_efficiency(),
            'feedback_loops': len(analyzer.find_feedback_loops())
        }
        print(json.dumps(results, indent=2))

    if args.export:
        analyzer.export_to_json(args.export)


if __name__ == '__main__':
    main()
