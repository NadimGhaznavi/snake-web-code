"""Format value changes captured in golden configuration decision events."""

import re

PAIR_PARAMETERS = {
    "epsilon_pair": (("epsilon", "initial"), ("epsilon", "decay")),
    "reward_pair": (("game", "rewards", "closer_to_food"),
                    ("game", "rewards", "further_from_food")),
}
from snake_web.constants.ReportLabels import FIELD_TO_LABEL_MAP


def parameter_change(decision: str | None, parameter: str | None = None) -> str:
    """Show recorded changes, ordering known pairs to match their display label."""
    number = r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"
    changes = re.findall(
        rf"(?:^|; )([\w.]+): ({number}) -> ({number})(?=; |\.$|$)",
        decision or "",
    )
    if len(changes) == 1:
        _, before, after = changes[0]
        return f"{before} > {after}"
    if parameter in PAIR_PARAMETERS:
        paths = [".".join(path) for path in PAIR_PARAMETERS[parameter]]
        by_path = {name: (before, after) for name, before, after in changes}
        if len(changes) == len(paths) and set(by_path) == set(paths):
            return ", ".join(f"{by_path[path][0]} > {by_path[path][1]}" for path in paths)
    return "; ".join(
        f"{FIELD_TO_LABEL_MAP.get(name, name)}: {before} > {after}"
        for name, before, after in changes
    )
