"""Values shown on the published experiment homepage."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExperimentStatus:
    all_time_highscore: int | None
    current_highscore: int | None
    simulations_submitted: int
    experiment_cycles: int
    snapshot: str | dict | None = None
