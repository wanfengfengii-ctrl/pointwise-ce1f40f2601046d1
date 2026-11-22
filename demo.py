from fractions import Fraction
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from bench.trial import trial
from exchange.issue import issue
from exchange.receipts import ReceiptStore
from exchange.receive import receive
from reports.export import export_report
from reports.lookup import get_report
from reports.store import ReportStore
from review.compare import sign
from station.instruments import register_instrument
from station.revision_store import RevisionStore
from station.revisions import import_revision


def main() -> None:
    sample_path = Path(__file__).resolve().parent / 'samples' / 'calibrations.json'
    sample = json.loads(sample_path.read_text(encoding='utf-8'))
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        station = RevisionStore(root / 'station.sqlite')
        center = root / 'center.sqlite'
        archive = root / 'station.offline'
        receipts, reports = ReceiptStore(center), ReportStore(center)
        station.initialize()
        receipts.initialize()
        reports.initialize()
        for instrument in sample['instruments']:
            register_instrument(station.path, **instrument)

        revisions = {}

        def intake(specification):
            instrument = specification['instrument']
            parent = specification.get('supersedes')
            revision = import_revision(station, instrument, specification['evidence'], specification['stages'],
                                       supersedes=None if parent is None else revisions[parent])
            revisions[specification['key']] = revision
            return receive(receipts, issue(station, revision).wire, instrument)

        old_spec, new_spec, corrected_spec = sample['revisions']
        old_receipt, new_receipt = intake(old_spec), intake(new_spec)
        endpoints = [trial(station, revisions['old'], setting).value for setting in (0, 2)]
        assert endpoints == [Fraction(2), Fraction(6)]
        station.path.rename(archive)
        assert not station.path.exists()
        request = sample['comparison']
        first = sign(receipts, reports, old_receipt, new_receipt, **request)
        archive.rename(station.path)
        corrected = intake(corrected_spec)
        station.path.rename(archive)
        updated = sign(receipts, reports, old_receipt, corrected, **request)

        reopened = ReportStore(center)
        assert get_report(reopened, first.report_id) == first
        assert get_report(reopened, updated.report_id) == updated
        assert not station.path.exists()
        first_export = json.loads(export_report(reopened, first.report_id))
        updated_export = json.loads(export_report(reopened, updated.report_id))
        expected_first = {'released': [['0', '2', True, True]], 'over_tolerance': [], 'no_common_evidence': []}
        expected_updated = {'released': [], 'over_tolerance': [['0', '2', True, True]], 'no_common_evidence': []}
        assert first_export['partition'] == expected_first
        assert updated_export['partition'] == expected_updated
        assert first_export['request']['receipts'] == [old_receipt, new_receipt]
        assert updated_export['request']['receipts'] == [old_receipt, corrected]
        print(json.dumps({'bench_outputs': [str(value) for value in endpoints],
                          'first_report': first_export, 'corrected_report': updated_export}, ensure_ascii=False))
        print('POINTWISE_SCENARIO ' + json.dumps({
            'case_id': 'v4',
            'input': {'request': request, 'old': ['x+1', '2t'], 'replacement': '2x+3'},
            'expected': expected_first, 'actual': first_export['partition'],
            'downstream_expected': {'old': expected_first, 'correction': expected_updated},
            'downstream_actual': {'old': first_export['partition'], 'correction': updated_export['partition']},
            'code_paths': ['bench/trial.py', 'exchange/issue.py', 'review/compare.py', 'reports/export.py'],
            'oracle': '两端和整窗旧表末值为 2x+2，初版常差 1，勘误后常差 2。',
        }, ensure_ascii=False))


if __name__ == '__main__':
    main()
