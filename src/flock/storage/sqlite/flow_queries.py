"""SQLite counts of what flowed where, for the dashboard's Agent View (#640).

Artifacts, consumptions and decisions are counted with ``GROUP BY``;
coverages are read a few JSON fields per row, not whole payloads. Every
count matches what :class:`~flock.storage.flow.FlowCounts` counts in memory.
"""

from __future__ import annotations

import json
from collections.abc import Collection, Mapping
from datetime import datetime
from typing import TYPE_CHECKING, Any

from flock.decisions.choice import UNSURE
from flock.decisions.graph import ITEM_RESULTS
from flock.storage.flow import FlowCounts


if TYPE_CHECKING:
    import aiosqlite


def _and(where_clause: str, condition: str) -> str:
    return f"{where_clause} AND {condition}" if where_clause else f" WHERE {condition}"


def _marks(values: list[str]) -> str:
    return ", ".join("?" for _ in values)


def _present(**fields: Any) -> dict[str, Any]:
    """A payload of the fields that are set, as a decision's own would be."""
    return {key: value for key, value in fields.items() if value is not None}


class SQLiteFlowQueries:
    """Counts a filter range of the ``artifacts`` table (aliased ``a``)."""

    async def count(
        self,
        conn: aiosqlite.Connection,
        where_clause: str,
        params: tuple[Any, ...],
        running: Mapping[str, Collection[str]],
    ) -> FlowCounts:
        from flock.decisions.graph import decision_label

        flow = FlowCounts()
        rows = await self._rows(
            conn,
            "SELECT a.produced_by, a.type, COUNT(*) FROM artifacts a"  # nosec B608
            f"{where_clause} GROUP BY a.produced_by, a.type",
            params,
        )
        for producer, type_name, count in rows:
            flow.produce(producer or "external", type_name, count)
        types = {type_name for _, type_name, _ in rows}
        decisions = sorted(t for t in types if flow.kind(t) == "decision")
        coverages = sorted(t for t in types if flow.kind(t) == "coverage")

        # Each artifact once per consumer, recorded or still running, in one
        # statement (a run that ends meanwhile counts once); a decision's
        # edge by its option
        is_decision = f"a.type IN ({_marks(decisions)})" if decisions else "0"
        columns = (
            "a.produced_by AS p, {consumer} AS c, a.type AS t,"
            f" CASE WHEN {is_decision} THEN json_extract(a.payload, '$.choice') END AS choice,"
            f" CASE WHEN {is_decision} THEN json_extract(a.payload, '$.kind') END AS kind,"
            f" CASE WHEN {is_decision} THEN json_extract(a.payload, '$.question') END AS question,"
            " a.artifact_id AS id, a.created_at AS at"
        )
        query = (
            f"SELECT {columns.format(consumer='c.consumer')}"  # nosec B608
            " FROM artifacts a"
            " JOIN artifact_consumptions c ON c.artifact_id = a.artifact_id"
            f"{where_clause}"
        )
        query_params: tuple[Any, ...] = (*decisions, *decisions, *decisions, *params)
        if running:
            unrecorded = (
                "NOT EXISTS (SELECT 1 FROM artifact_consumptions k"
                " WHERE k.artifact_id = r.artifact_id AND k.consumer = r.consumer)"
            )
            query += (
                f" UNION ALL SELECT {columns.format(consumer='r.consumer')}"  # nosec B608
                " FROM (SELECT json_extract(value, '$[0]') AS artifact_id,"
                " json_extract(value, '$[1]') AS consumer FROM json_each(?)) r"
                " JOIN artifacts a ON a.artifact_id = r.artifact_id"
                f"{_and(where_clause, unrecorded)}"
            )
            pairs = [
                [artifact_id, consumer]
                for artifact_id, consumers in running.items()
                for consumer in consumers
            ]
            query_params += (
                *decisions,
                *decisions,
                *decisions,
                json.dumps(pairs),
                *params,
            )
        rows = await self._rows(
            conn,
            "SELECT p, c, t, choice, kind, question, COUNT(DISTINCT id), MAX(at)"  # nosec B608
            f" FROM ({query}) AS flow"
            " GROUP BY 1, 2, 3, 4, 5, 6",
            query_params,
        )
        for (
            producer,
            consumer,
            type_name,
            choice,
            kind,
            question,
            count,
            newest,
        ) in rows:
            label = (
                decision_label(_present(choice=choice, kind=kind, question=question))
                if type_name in decisions
                else None
            )
            flow.consume(
                producer or "external",
                consumer,
                type_name,
                label,
                datetime.fromisoformat(newest),
                count,
            )

        if decisions:
            await self._count_decisions(conn, flow, where_clause, params, decisions)

        if coverages:
            rows = await self._rows(
                conn,
                "SELECT a.produced_by, a.type,"  # nosec B608
                " json_extract(a.payload, '$.group'),"
                " json_extract(a.payload, '$.revision'),"
                " json_extract(a.payload, '$.choice'), a.created_at"
                " FROM artifacts a"
                f"{_and(where_clause, f'a.type IN ({_marks(coverages)})')}",
                (*params, *coverages),
            )
            for producer, type_name, group, revision, choice, at in rows:
                flow.cover(
                    producer or "external",
                    type_name,
                    _present(group=group, revision=revision, choice=choice),
                    datetime.fromisoformat(at),
                )
        return flow

    async def _count_decisions(
        self,
        conn: aiosqlite.Connection,
        flow: FlowCounts,
        where_clause: str,
        params: tuple[Any, ...],
        decisions: list[str],
    ) -> None:
        """Tally decisions per producer, type and option in SQL; read the
        checklist items, unsure decisions and reviews only where there are
        any."""
        shadowed = (
            "(json_type(a.payload, '$.shadow') = 'object'"
            " AND json_extract(a.payload, '$.shadow') != '{}'"
            " AND json_type(a.payload, '$.shadow.error') IS NULL)"
        )
        rows = await self._rows(
            conn,
            "SELECT a.produced_by, a.type,"  # nosec B608
            " json_extract(a.payload, '$.choice'), json_extract(a.payload, '$.kind'),"
            " COUNT(*), SUM(json_extract(a.payload, '$.refused')),"
            " SUM(json_extract(a.payload, '$.score')),"
            " COUNT(json_extract(a.payload, '$.score')),"
            f" SUM({shadowed}),"
            f" SUM({shadowed} AND json_extract(a.payload, '$.shadow.choice')"
            " IS json_extract(a.payload, '$.choice')),"
            " COUNT(json_extract(a.payload, '$.review_of'))"
            " FROM artifacts a"
            f"{_and(where_clause, f'a.type IN ({_marks(decisions)})')}"
            " GROUP BY 1, 2, 3, 4",
            (*params, *decisions),
        )
        checklists, unsure, reviews = set(), set(), set()
        for producer, type_name, choice, kind, count, *sums in rows:
            refused, score_total, scored, compared, agree, reviewing = sums
            tally = flow.tally(producer or "external", type_name)
            tally.counts[choice] = tally.counts.get(choice, 0) + count
            tally.refused += refused or 0
            tally.score_total += score_total or 0
            tally.scored += scored
            tally.shadow_compared += compared or 0
            tally.shadow_agree += agree or 0
            if kind == "checklist":
                checklists.add(type_name)
            elif choice == UNSURE:
                unsure.add(type_name)
            if reviewing:
                reviews.add(type_name)

        if checklists:
            rows = await self._rows(
                conn,
                "SELECT a.produced_by, a.type, item.key, item.value, COUNT(*)"  # nosec B608
                " FROM artifacts a, json_each(a.payload, '$.results') AS item"
                f"{_and(where_clause, f'a.type IN ({_marks(sorted(checklists))})')}"
                " GROUP BY 1, 2, 3, 4",
                (*params, *sorted(checklists)),
            )
            for producer, type_name, item, result, count in rows:
                if result in ITEM_RESULTS:
                    stats = flow.tally(producer or "external", type_name).items
                    stats.setdefault(item, [0, 0, 0])[ITEM_RESULTS.index(result)] += (
                        count
                    )
        if unsure:
            rows = await self._rows(
                conn,
                "SELECT a.artifact_id, a.produced_by, a.type, a.created_at"  # nosec B608
                " FROM artifacts a"
                + _and(
                    where_clause,
                    f"a.type IN ({_marks(sorted(unsure))})"
                    " AND json_extract(a.payload, '$.choice') = ?"
                    " AND COALESCE(json_extract(a.payload, '$.kind'), 'choice')"
                    " != 'checklist'"
                    " AND json_extract(a.payload, '$.review_of') IS NULL",
                ),
                (*params, *sorted(unsure), UNSURE),
            )
            for artifact_id, producer, type_name, at in rows:
                flow.wait(
                    artifact_id,
                    producer or "external",
                    type_name,
                    datetime.fromisoformat(at),
                )
        if reviews:
            rows = await self._rows(
                conn,
                "SELECT json_extract(a.payload, '$.review_of')"  # nosec B608
                " FROM artifacts a"
                + _and(
                    where_clause,
                    f"a.type IN ({_marks(sorted(reviews))})"
                    " AND json_extract(a.payload, '$.review_of') IS NOT NULL",
                ),
                (*params, *sorted(reviews)),
            )
            flow.reviewed.update(str(review_of) for (review_of,) in rows)

    @staticmethod
    async def _rows(
        conn: aiosqlite.Connection, query: str, params: tuple[Any, ...]
    ) -> list[tuple[Any, ...]]:
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        await cursor.close()
        return [tuple(row) for row in rows]


__all__ = ["SQLiteFlowQueries"]
