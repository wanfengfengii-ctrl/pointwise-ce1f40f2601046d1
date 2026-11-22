from dataclasses import dataclass
from pathlib import Path
from contextlib import closing
import sqlite3


@dataclass(frozen=True)
class Instrument:
    instrument_id: str
    label: str
    unit: str


def open_station(path: str | Path, mode: str) -> sqlite3.Connection:
    uri = Path(path).absolute().as_uri() + '?mode=' + mode
    connection = sqlite3.connect(uri, uri=True)
    connection.execute('PRAGMA foreign_keys = ON')
    return connection


def instrument_at(connection: sqlite3.Connection, instrument_id: str) -> Instrument:
    if not isinstance(instrument_id, str) or not instrument_id.strip():
        raise ValueError('instrument ID must be nonempty text')
    row = connection.execute(
        'SELECT instrument_id, label, unit FROM instruments WHERE instrument_id = ?',
        (instrument_id,),
    ).fetchone()
    if row is None:
        raise KeyError(instrument_id)
    return Instrument(*row)


def register_instrument(path: str | Path, instrument_id: str, label: str, unit: str) -> Instrument:
    fields = (instrument_id, label, unit)
    if any(not isinstance(field, str) or not field.strip() for field in fields):
        raise ValueError('instrument ID, label and unit are required')
    requested = Instrument(*fields)
    with closing(open_station(path, 'rw')) as connection, connection:
        connection.execute(
            'INSERT INTO instruments (instrument_id, label, unit) VALUES (?, ?, ?) '
            'ON CONFLICT (instrument_id) DO NOTHING',
            fields,
        )
        if instrument_at(connection, instrument_id) != requested:
            raise ValueError('instrument ID already has a different registration')
    return requested


def get_instrument(path: str | Path, instrument_id: str) -> Instrument:
    with closing(open_station(path, 'ro')) as connection:
        return instrument_at(connection, instrument_id)
