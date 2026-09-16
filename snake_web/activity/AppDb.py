"""Application queries for Snake Lab and Ax3l experiment data."""

import json

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
