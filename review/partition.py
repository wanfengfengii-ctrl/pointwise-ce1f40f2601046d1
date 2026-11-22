from collections.abc import Iterable
from dataclasses import dataclass

from review.endpoints import Endpoint, compare_endpoints


@dataclass(frozen=True)
class DecisionInterval:
    lower: Endpoint
    upper: Endpoint
    lower_closed: bool = True
    upper_closed: bool = True

    def __post_init__(self) -> None:
        if type(self.lower_closed) is not bool or type(self.upper_closed) is not bool:
            raise ValueError('interval flags must be booleans')
        order = compare_endpoints(self.lower, self.upper)
        if order > 0 or (order == 0 and not (self.lower_closed and self.upper_closed)):
            raise ValueError('empty or reversed decision interval')

    def contains(self, point: Endpoint) -> bool:
        lo = compare_endpoints(point, self.lower)
        hi = compare_endpoints(point, self.upper)
        return (lo > 0 or lo == 0 and self.lower_closed) and (hi < 0 or hi == 0 and self.upper_closed)


@dataclass(frozen=True)
class DecisionPartition:
    released: tuple[DecisionInterval, ...]
    over_tolerance: tuple[DecisionInterval, ...]
    no_common_evidence: tuple[DecisionInterval, ...]


_CATEGORIES = ('released', 'over_tolerance', 'no_common_evidence')


def assemble_partition(atoms: Iterable[tuple[str, DecisionInterval]]) -> DecisionPartition:
    groups: dict[str, list[DecisionInterval]] = {category: [] for category in _CATEGORIES}
    previous = None
    previous_category = None
    for category, atom in atoms:
        if category not in groups:
            raise ValueError('unknown quality decision')
        if previous is None:
            if not atom.lower_closed:
                raise ValueError('the first window endpoint is missing')
        elif (compare_endpoints(previous.upper, atom.lower) != 0
              or previous.upper_closed == atom.lower_closed):
            raise ValueError('decision atoms must cover the window without gaps or overlap')
        group = groups[category]
        if category == previous_category:
            original = group.pop()
            group.append(DecisionInterval(original.lower, atom.upper, original.lower_closed, atom.upper_closed))
        else:
            group.append(atom)
        previous, previous_category = atom, category
    if previous is None or not previous.upper_closed:
        raise ValueError('the last window endpoint is missing')
    return DecisionPartition(*(tuple(groups[name]) for name in _CATEGORIES))
