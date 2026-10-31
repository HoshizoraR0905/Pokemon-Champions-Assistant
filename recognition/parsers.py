import re
from dataclasses import replace
from models import Observation


def ratio(observation: Observation) -> Observation:
    text = re.sub(r"\s+", "", str(observation.value or ""))
    match = re.fullmatch(r"(\d{1,4})/(\d{1,4})", text)
    value = None
    if match:
        current, maximum = map(int, match.groups())
        if 0 <= current <= maximum and maximum > 0:
            value = {"current": current, "maximum": maximum}
    return replace(observation, value=value)


def percentage(observation: Observation) -> Observation:
    match = re.fullmatch(r"(\d{1,3})%", re.sub(r"\s+", "", str(observation.value if observation.value is not None else "")))
    value = int(match[1]) if match and int(match[1]) <= 100 else None
    return replace(observation, value=value)
