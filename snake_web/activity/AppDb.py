"""Application queries for Snake Lab and Ax3l experiment data."""

import json

from snake_web.constants.PublicEvents import EVENT_LABELS, CONFIGURATION_FIELDS
from snake_web.entity.ExperimentStatus import ExperimentStatus
from snake_web.interface.DbMgr import DbMgr


def completed_cycles(rows: list[dict]) -> int:
    """Count complete ordered passes, ignoring duplicate comparisons and gaps.

    Ax3l records the parameter order in each checkpoint. Read that order rather
    than importing Ax3l's application code or guessing cycles from run counts.
    """
    cycles, expected = 0, 0
    order = None
    seen = set()
    for row in rows:
        if row['process_id'] in seen:
            continue
        seen.add(row['process_id'])
        checkpoint = json.loads(row['content'])
        saved_order, index = checkpoint['parameter_order'], checkpoint['index']
        if (not isinstance(saved_order, list) or not saved_order
                or any(not isinstance(name, str) for name in saved_order)
                or type(index) is not int or not 0 <= index < len(saved_order)):
            raise ValueError('Invalid round-robin checkpoint')
        if order is not None and saved_order != order:
            raise ValueError('Search parameter order changed; cannot count experiment cycles')
        order = saved_order
        if index != expected:
            expected = 0
            if index != 0:
                continue
        expected += 1
        if expected == len(order):
            cycles += 1
            expected = 0
    return cycles


class AppDb:
    def __init__(self, db: DbMgr):
        self._db = db

    def get_current_highscore(self) -> int | None:
        """Highest recorded score across all runs; None before any score exists."""
        return self._db.query(
            "SELECT MAX(high_score) AS high_score FROM simulation_runs"
        )[0]["high_score"]

    def get_experiment_status(self) -> ExperimentStatus:
        totals = self._db.query("""
            SELECT MAX(high_score) AS high_score, COUNT(*) AS simulations
            FROM simulation_runs
        """)[0]
        # Match the report server's latest golden creation, not the newest run
        # or the all-time winner (which may belong to an earlier seed).
        golden = self._db.query("""
            SELECT e.process_id FROM ax3l.events e
            JOIN ax3l.event_messages m USING (event_id)
            WHERE e.category = 'Configuration' AND e.name = 'golden_config_created'
            ORDER BY e.occurred_at DESC, e.event_id DESC LIMIT 1
        """)
        # Pass the ID as a value: the two schemas currently use different
        # collations, so comparing their text columns directly fails.
        current = self._db.query(
            "SELECT high_score, high_score_snapshot FROM simulation_runs WHERE run_id = %s",
            (golden[0]['process_id'],),
        ) if golden else []
        comparisons = self._db.query("""
            SELECT c.process_id, m.content
            FROM ax3l.events c
            JOIN ax3l.events p ON p.event_id = (
                SELECT MIN(event_id) FROM ax3l.events
                WHERE process_id = c.process_id AND category = 'Configuration'
                  AND name = 'proposal_accepted')
            JOIN ax3l.events checkpoint ON checkpoint.event_id = (
                SELECT MAX(event_id) FROM ax3l.events
                WHERE event_id < p.event_id AND category = 'Configuration'
                  AND name = 'round_robin_checkpoint')
            JOIN ax3l.event_messages m ON m.event_id = checkpoint.event_id
            WHERE c.category = 'Configuration' AND c.name = 'configuration_compared'
            ORDER BY c.event_id
        """)
        return ExperimentStatus(
            all_time_highscore=totals['high_score'],
            current_highscore=current[0]['high_score'] if current else None,
            simulations_submitted=totals['simulations'],
            experiment_cycles=completed_cycles(comparisons),
            snapshot=current[0]['high_score_snapshot'] if current else None,
        )

    def get_highscore_history(self, after_event_id: int) -> list[dict]:
        """Accepted scores in decision order, including lower seed baselines."""
        return self._db.query("""
            SELECT event_id, simulations, score, seed
            FROM ax3l.experiment_highscores
            WHERE event_id > %s ORDER BY event_id
        """, (after_event_id,))

    def get_run_scores(self) -> list[dict]:
        """Read mutable scores in the same submission order as Ax3l's histogram.

        There is no score-change cursor in the source schema. Compare this small
        projection to the CSV so updates to earlier runs are never missed.
        """
        return self._db.query(
            "SELECT id, high_score FROM simulation_runs ORDER BY id"
        )

    def get_top_runs(self) -> list[dict]:
        """Rank scored simulations, using submission ID to break score ties."""
        return self._db.query("""
            SELECT id, high_score, high_score_snapshot FROM simulation_runs
            WHERE high_score IS NOT NULL
            ORDER BY high_score DESC, id ASC LIMIT 100
        """)

    def get_golden_configurations(self, after_event_id: int) -> list[dict]:
        """Include every baseline/promotion and the response that proposed its run."""
        return self._db.query("""
            WITH successful_tools AS (
                SELECT e.event_id, e.process_id,
                       JSON_UNQUOTE(JSON_EXTRACT(CASE WHEN JSON_VALID(m.content) THEN m.content ELSE '{}' END,
                                                 '$.run_id')) AS run_id
                FROM ax3l.events e JOIN ax3l.event_messages m USING (event_id)
                WHERE e.category = 'Tool' AND e.name = 'tool_execution_completed'
                  AND JSON_UNQUOTE(JSON_EXTRACT(CASE WHEN JSON_VALID(m.content) THEN m.content ELSE '{}' END,
                                               '$.status')) = 'ok'
            )
            SELECT g.event_id, g.occurred_at, g.process_id, p.parameter, h.score AS high_score,
                   r.event_id AS reply_id, rm.content AS response, gm.content AS decision
            FROM ax3l.events g
            LEFT JOIN ax3l.event_messages gm ON gm.event_id = g.event_id
            LEFT JOIN ax3l.experiment_highscores h ON h.event_id = g.event_id
            LEFT JOIN successful_tools t ON t.event_id = (
                SELECT MIN(event_id) FROM successful_tools WHERE run_id = g.process_id)
            LEFT JOIN ax3l.events r ON r.event_id = (
                SELECT MAX(event_id) FROM ax3l.events
                WHERE process_id = t.process_id AND event_id < t.event_id
                  AND category = 'Conversation' AND name = 'reply_received')
            LEFT JOIN ax3l.event_messages rm ON rm.event_id = r.event_id
            LEFT JOIN ax3l.events p ON p.event_id = (
                SELECT MAX(event_id) FROM ax3l.events
                WHERE process_id = r.process_id AND event_id < r.event_id
                  AND category = 'Conversation' AND name = 'prompt_sent')
            WHERE g.category = 'Configuration' AND g.name = 'golden_config_created'
              AND g.event_id > %s
            ORDER BY g.event_id
        """, (after_event_id,))

    def get_event_export_end(self) -> int:
        # MariaDB can type this aggregate expression as DECIMAL. The application
        # cursor is an integer, including when the event table is empty.
        return int(self._db.query(
            "SELECT COALESCE(MAX(event_id), 0) AS event_id FROM ax3l.events"
        )[0]['event_id'])

    def get_public_events(self, after_event_id: int, through_event_id: int) -> list[dict]:
        clauses = ' OR '.join('(e.category = %s AND e.name = %s)' for _ in EVENT_LABELS)
        kinds = tuple(value for pair in EVENT_LABELS for value in pair)
        return self._db.query(f"""
            SELECT e.event_id, e.occurred_at, e.category, e.name, e.log_level,
                   e.process_id, e.source_name, e.parameter, e.parent_event_id, e.ax3l_version, m.content
            FROM ax3l.events e LEFT JOIN ax3l.event_messages m USING (event_id)
            WHERE e.event_id > %s AND e.event_id <= %s AND ({clauses})
            ORDER BY e.event_id LIMIT 250
        """, (after_event_id, through_event_id, *kinds))

    def get_public_simulations(self, run_ids: list[str]) -> list[dict]:
        if not run_ids:
            return []
        columns = ', '.join('c.' + column for column, _, _ in CONFIGURATION_FIELDS)
        placeholders = ', '.join('%s' for _ in run_ids)
        rows = self._db.query(f"""
            SELECT r.run_id, r.project_version, r.high_score, r.completed_at,
                   r.high_score_snapshot, {columns}
            FROM simulation_runs r LEFT JOIN configurations c ON c.run_id = r.run_id
            WHERE r.run_id IN ({placeholders}) ORDER BY r.id
        """, tuple(run_ids))
        for row in rows:
            config = {}
            for column, path, kind in CONFIGURATION_FIELDS:
                value = row.pop(column)
                if value is None:
                    continue
                target = config
                for part in path[:-1]:
                    target = target.setdefault(part, {})
                target[path[-1]] = int(value) if kind == 'integer' else float(value)
            row['configuration'] = config
        return rows
