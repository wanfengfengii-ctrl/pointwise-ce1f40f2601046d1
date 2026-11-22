from bench.stages import parse_stage
from station.evidence import validate_evidence
from station.revision_store import RevisionStore


class InvalidRevision(ValueError):
    """The candidate revision cannot be frozen."""


def import_revision(store: RevisionStore, instrument_id: str, evidence: object,
                    stages: object, supersedes: int | None = None) -> int:
    try:
        original = validate_evidence(evidence)
        if not isinstance(stages, (list, tuple)) or not stages:
            raise ValueError('a revision requires an ordered, nonempty stage list')
        conversions = tuple(parse_stage(raw) for raw in stages)
        return store.append(instrument_id, original, conversions, supersedes)
    except (ValueError, KeyError) as error:
        raise InvalidRevision(str(error)) from error
