from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from unittest import TestCase

from exchange.issue import issue
from exchange.receipts import ReceiptStore
from exchange.receive import receive
from reports.store import ReportStore
from station.instruments import register_instrument
from station.revision_store import RevisionStore
from station.revisions import import_revision


IDENTITY = (1, 0, 0, 1)
RECIPROCAL = (0, 1, 1, 0)
CANCELING_MAP = (1, 0, 1, -1)


def stage(name, coefficients, limits=None, evidence='primary'):
    return {'name': name, 'map': list(coefficients), 'range': limits, 'evidence': evidence}


def ordinary_old():
    return [stage('offset', (1, 1, 0, 1), [0, 2]),
            stage('gain', (2, 0, 0, 1), [1, 3], 'secondary')]


def canceling_chain():
    return [stage('meter', CANCELING_MAP), stage('converter', CANCELING_MAP, evidence='secondary')]


def table_counts(path, *tables):
    with closing(sqlite3.connect(path)) as connection:
        return tuple(connection.execute(f'SELECT count(*) FROM {table}').fetchone()[0] for table in tables)


class HandoverCase(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.station_path = root / 'station.sqlite'
        self.archive = root / 'station.offline'
        self.center_path = root / 'center.sqlite'
        self.station = RevisionStore(self.station_path)
        self.receipts = ReceiptStore(self.center_path)
        self.reports = ReportStore(self.center_path)
        self.station.initialize()
        self.receipts.initialize()
        self.reports.initialize()
        register_instrument(self.station_path, 'OLD-A', '旧表 A', 'bar')
        register_instrument(self.station_path, 'NEW-B', '换装表 B', 'bar')

    def freeze(self, instrument, stages, source, supersedes=None):
        evidence = {'source': source, 'records': {'primary': '原校验单首项', 'secondary': '原校验单后项'}}
        return import_revision(self.station, instrument, evidence, stages, supersedes=supersedes)

    def accept(self, revision, instrument):
        return receive(self.receipts, issue(self.station, revision).wire, instrument)

    def install_pair(self, old_stages, new_stages):
        old = self.freeze('OLD-A', old_stages, '旧表初版')
        new = self.freeze('NEW-B', new_stages, '换装表初版')
        return (old, new), (self.accept(old, 'OLD-A'), self.accept(new, 'NEW-B'))

    def detach_station(self):
        self.station_path.rename(self.archive)
        self.assertFalse(self.station_path.exists())

    def receipt_count(self):
        return table_counts(self.center_path, 'received_pieces')[0]

    def signed_counts(self):
        return table_counts(self.center_path, 'reports', 'report_receipts')
