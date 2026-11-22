from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import sqlite3

from exchange.calibration_body import CalibrationBody, decode_body
from exchange.envelope import PieceOrigin, V1Envelope, canonical_json, read_json, valid_number


def open_center(path: str | Path, mode: str) -> sqlite3.Connection:
    uri = Path(path).absolute().as_uri() + '?mode=' + mode
    connection = sqlite3.connect(uri, uri=True)
    connection.execute('PRAGMA foreign_keys = ON')
    return connection


@dataclass(frozen=True)
class ReceivedPiece:
    receipt_id: int
    origin: PieceOrigin
    body: CalibrationBody
    digest: str


class ReceiptStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def initialize(self) -> None:
        with closing(open_center(self.path, 'rwc')) as connection, connection:
            connection.execute('''
                CREATE TABLE IF NOT EXISTS received_pieces (
                    id INTEGER PRIMARY KEY,
                    origin TEXT NOT NULL,
                    body TEXT NOT NULL,
                    digest TEXT NOT NULL
                )
            ''')

    def record(self, envelope: V1Envelope, body: CalibrationBody) -> int:
        if decode_body(envelope.body) != body:
            raise ValueError('validated evidence does not match the received text')
        with closing(open_center(self.path, 'rw')) as connection, connection:
            receipt_id = connection.execute(
                'INSERT INTO received_pieces (origin, body, digest) VALUES (?, ?, ?)',
                (canonical_json(envelope.origin.as_data()), envelope.body, envelope.digest),
            ).lastrowid
        return receipt_id

    def get(self, receipt_id: int) -> ReceivedPiece:
        if not valid_number(receipt_id):
            raise KeyError(receipt_id)
        with closing(open_center(self.path, 'ro')) as connection:
            row = connection.execute(
                'SELECT origin, body, digest FROM received_pieces WHERE id = ?', (receipt_id,),
            ).fetchone()
        if row is None:
            raise KeyError(receipt_id)
        origin, body, digest = row
        return ReceivedPiece(receipt_id, PieceOrigin.from_data(read_json(origin)), decode_body(body), digest)
