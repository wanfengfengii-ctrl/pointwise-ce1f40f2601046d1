from contextlib import closing
from dataclasses import dataclass
import json
from pathlib import Path

from bench.stages import CalibrationStage, parse_stage, stage_data
from station.evidence import CalibrationEvidence, decode_evidence, encode_evidence
from station.instruments import Instrument, instrument_at, open_station


@dataclass(frozen=True)
class FrozenRevision:
    revision_id: int
    instrument: Instrument
    evidence: CalibrationEvidence
    stages: tuple[CalibrationStage, ...]
    supersedes: int | None


def _check_revision_id(revision_id: int) -> None:
    if type(revision_id) is not int or not 1 <= revision_id < 2**63:
        raise ValueError('revision ID must be a positive SQLite integer')


class RevisionStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def initialize(self) -> None:
        with closing(open_station(self.path, 'rwc')) as connection:
            connection.executescript('''
                BEGIN;
                CREATE TABLE IF NOT EXISTS instruments (
                    instrument_id TEXT PRIMARY KEY NOT NULL,
                    label TEXT NOT NULL,
                    unit TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS calibration_evidence (
                    id INTEGER PRIMARY KEY,
                    content TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS revisions (
                    id INTEGER PRIMARY KEY,
                    instrument_id TEXT NOT NULL REFERENCES instruments(instrument_id),
                    evidence_id INTEGER NOT NULL UNIQUE REFERENCES calibration_evidence(id),
                    supersedes INTEGER REFERENCES revisions(id)
                );
                CREATE TABLE IF NOT EXISTS revision_stages (
                    revision_id INTEGER NOT NULL REFERENCES revisions(id),
                    position INTEGER NOT NULL CHECK (position >= 0),
                    content TEXT NOT NULL,
                    PRIMARY KEY (revision_id, position)
                );
                COMMIT;
            ''')

    def append(self, instrument_id: str, evidence: CalibrationEvidence,
               stages: tuple[CalibrationStage, ...], supersedes: int | None = None) -> int:
        if not stages or len({stage.name for stage in stages}) != len(stages):
            raise ValueError('a revision requires nonempty, uniquely named stages')
        reference_ids = {reference for reference, _ in evidence.records}
        for stage in stages:
            if stage.evidence_ref not in reference_ids:
                raise ValueError(f'{stage.name!r} refers to an unknown evidence record')
        evidence_text = encode_evidence(evidence)
        stage_texts = tuple(json.dumps(stage_data(stage), ensure_ascii=False) for stage in stages)
        if supersedes is not None:
            _check_revision_id(supersedes)
        with closing(open_station(self.path, 'rw')) as connection, connection:
            connection.execute('BEGIN IMMEDIATE')
            instrument_at(connection, instrument_id)
            if supersedes is not None:
                previous = connection.execute(
                    'SELECT instrument_id FROM revisions WHERE id = ?', (supersedes,),
                ).fetchone()
                if previous is None or previous[0] != instrument_id:
                    raise ValueError('a correction must name an existing revision of the same instrument')
            evidence_id = connection.execute(
                'INSERT INTO calibration_evidence (content) VALUES (?)', (evidence_text,),
            ).lastrowid
            revision_id = connection.execute(
                'INSERT INTO revisions (instrument_id, evidence_id, supersedes) VALUES (?, ?, ?)',
                (instrument_id, evidence_id, supersedes),
            ).lastrowid
            connection.executemany(
                'INSERT INTO revision_stages (revision_id, position, content) VALUES (?, ?, ?)',
                ((revision_id, index, text) for index, text in enumerate(stage_texts)),
            )
        return revision_id

    def get(self, revision_id: int) -> FrozenRevision:
        _check_revision_id(revision_id)
        with closing(open_station(self.path, 'ro')) as connection:
            row = connection.execute('''
                SELECT r.instrument_id, e.content, r.supersedes
                FROM revisions AS r JOIN calibration_evidence AS e ON e.id = r.evidence_id
                WHERE r.id = ?
            ''', (revision_id,)).fetchone()
            if row is None:
                raise KeyError(revision_id)
            instrument_id, evidence_text, supersedes = row
            instrument = instrument_at(connection, instrument_id)
            stage_rows = connection.execute(
                'SELECT content FROM revision_stages WHERE revision_id = ? ORDER BY position',
                (revision_id,),
            )
            stages = tuple(parse_stage(json.loads(text)) for (text,) in stage_rows)
        return FrozenRevision(revision_id, instrument, decode_evidence(evidence_text), stages, supersedes)
