from fractions import Fraction as Q

from bench.traces import StageReading, UnavailableStage
from bench.trial import run_trial, trial
from station.instruments import get_instrument, register_instrument
from station.revisions import InvalidRevision
from tests.support import HandoverCase, IDENTITY, ordinary_old, stage, table_counts


class TestStation(HandoverCase):
    def test_closed_boundary(self):
        revision = self.freeze('OLD-A', ordinary_old(), '原单 A')
        for setting, first, output in ((0, 1, 2), (2, 3, 6)):
            with self.subTest(setting=setting):
                trace = trial(self.station, revision, setting)
                self.assertTrue(trace.completed)
                self.assertEqual(trace.value, Q(output))
                self.assertEqual(trace.readings, (StageReading('offset', Q(setting), Q(first), 'primary'),
                                                  StageReading('gain', Q(first), Q(output), 'secondary')))
        frozen = self.station.get(revision)
        self.assertEqual(frozen.evidence.source, '原单 A')
        self.assertEqual(frozen.evidence.record('secondary'), '原校验单后项')
        self.assertEqual(get_instrument(self.station_path, 'OLD-A'), frozen.instrument)

    def test_next_stage_input(self):
        stages = [stage('offset', (1, 1, 0, 1), [0, 3]),
                  stage('gain', (2, 0, 0, 1), [1, 3], 'secondary')]
        revision = self.freeze('OLD-A', stages, '不同坐标的后级量程')
        frozen = self.station.get(revision)
        preflight = run_trial(frozen.stages, 0)
        self.assertEqual(preflight, trial(self.station, revision, 0))
        self.assertEqual(preflight.readings[1].input_value, Q(1))
        self.assertEqual(preflight.value, Q(2))
        failed = trial(self.station, revision, 3)
        self.assertEqual(failed.readings, (StageReading('offset', Q(3), Q(4), 'primary'),))
        self.assertEqual(failed.unavailable, UnavailableStage('gain', Q(4), 'secondary', 'out_of_range'))
        self.assertIsNone(failed.value)

    def test_pole_at_closed_edge(self):
        stages = [stage('offset', (1, 1, 0, 1), [0, 2]),
                  stage('ratio', (0, 1, 1, -1), [1, 3], 'secondary')]
        revision = self.freeze('OLD-A', stages, '下端为极点')
        rejected = trial(self.station, revision, 0)
        self.assertFalse(rejected.completed)
        self.assertEqual(rejected.readings, (StageReading('offset', Q(0), Q(1), 'primary'),))
        self.assertEqual(rejected.unavailable, UnavailableStage('ratio', Q(1), 'secondary', 'pole'))
        self.assertIsNone(rejected.value)
        self.assertEqual(trial(self.station, revision, 2).value, Q(1, 2))

    def test_bad_revision(self):
        revision = self.freeze('OLD-A', ordinary_old(), '合格原单')
        names = ('instruments', 'calibration_evidence', 'revisions', 'revision_stages')
        baseline = table_counts(self.station_path, *names)
        good = stage('first', IDENTITY, [0, 2])
        for malformed in (stage('second', (1, '3/0', 0, 1)), stage('second', IDENTITY, [2, 0]),
                          stage('second', IDENTITY, evidence='unknown'), stage('first', IDENTITY)):
            with self.subTest(stage=malformed), self.assertRaises(InvalidRevision):
                self.freeze('OLD-A', [good, malformed], '非法勘误', revision)
            self.assertEqual(table_counts(self.station_path, *names), baseline)
        with self.assertRaises(InvalidRevision):
            self.freeze('NEW-B', [good], '错表前版', revision)
        self.assertEqual(table_counts(self.station_path, *names), baseline)
        self.assertEqual(self.station.get(revision).evidence.source, '合格原单')
        self.assertEqual(trial(self.station, revision, '1/2').value, Q(3))

    def test_bad_trial_and_duplicate_registration(self):
        revision = self.freeze('OLD-A', [stage('identity', IDENTITY)], '原单')
        with self.assertRaises(KeyError):
            trial(self.station, revision + 100, 0)
        for value in (True, None, 0.5, ''):
            with self.subTest(value=value), self.assertRaises(ValueError):
                trial(self.station, revision, value)
        register_instrument(self.station_path, 'OLD-A', '旧表 A', 'bar')
        with self.assertRaises(ValueError):
            register_instrument(self.station_path, 'OLD-A', '旧表 A', 'psi')
        self.assertEqual(get_instrument(self.station_path, 'OLD-A').unit, 'bar')
