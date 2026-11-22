from fractions import Fraction as Q
import json

from exchange.calibration_body import SupportInterval
from exchange.envelope import encode_envelope, verify_envelope
from exchange.issue import issue
from exchange.receive import RejectedPiece, receive
from tests.support import HandoverCase, IDENTITY, canceling_chain, stage


class TestExchange(HandoverCase):
    def test_fixed_revision(self):
        original = self.freeze('NEW-B', [stage('gain', (2, 3, 0, 1))], 'B 初版原单')
        corrected = self.freeze('NEW-B', [stage('gain', (2, 4, 0, 1))], 'B 勘误原单', original)
        self.assertEqual(self.station.get(corrected).supersedes, original)
        first = issue(self.station, original)
        second = issue(self.station, corrected)
        self.assertEqual(first.wire, issue(self.station, original).wire)
        self.assertNotIn('原校验单首项', json.loads(first.wire)['body'])
        self.assertNotIn('gain', json.loads(first.wire)['body'])
        first_id = receive(self.receipts, first.wire, 'NEW-B')
        second_id = receive(self.receipts, second.wire, 'NEW-B')
        self.detach_station()
        for number, revision, source, value in ((first_id, original, 'B 初版原单', 3),
                                                (second_id, corrected, 'B 勘误原单', 4)):
            with self.subTest(revision=revision):
                piece = self.receipts.get(number)
                self.assertEqual((piece.origin.revision_id, piece.origin.source), (revision, source))
                self.assertEqual(piece.body.terminal.value_at(0), Q(value))
        self.assertNotEqual(first_id, second_id)

    def test_original_support(self):
        first = self.freeze('OLD-A', canceling_chain(), '有孔初版')
        second = self.freeze('OLD-A', [stage('full', IDENTITY)], '恒等勘误', first)
        old_id = self.accept(first, 'OLD-A')
        new_id = self.accept(second, 'OLD-A')
        self.detach_station()
        old_piece, new_piece = self.receipts.get(old_id), self.receipts.get(new_id)
        self.assertEqual((old_piece.origin.revision_id, new_piece.origin.revision_id), (first, second))
        self.assertEqual(old_piece.body.terminal, new_piece.body.terminal)
        self.assertEqual(old_piece.body.support, (SupportInterval(None, Q(1)), SupportInterval(Q(1), None)))
        self.assertEqual(new_piece.body.support, (SupportInterval(None, None),))
        for setting, old_allowed in ((0, True), (1, False), (2, True)):
            with self.subTest(setting=setting):
                self.assertEqual(old_piece.body.supports(setting), old_allowed)
                self.assertTrue(new_piece.body.supports(setting))
                if old_allowed:
                    self.assertEqual(old_piece.body.terminal.value_at(setting), Q(setting))

    def test_wrong_instrument(self):
        revision = self.freeze('NEW-B', [stage('identity', IDENTITY)], '乙表原单')
        piece = issue(self.station, revision)
        with self.assertRaises(RejectedPiece):
            receive(self.receipts, piece.wire, 'OLD-A')
        self.assertEqual(self.receipt_count(), 0)
        accepted = receive(self.receipts, piece.wire, 'NEW-B')
        self.assertEqual(self.receipts.get(accepted).origin.instrument_id, 'NEW-B')
        self.assertEqual(self.receipt_count(), 1)

    def test_damaged_piece(self):
        revision = self.freeze('OLD-A', [stage('identity', IDENTITY)], '甲表原单')
        piece = issue(self.station, revision)
        changed = json.loads(piece.wire)
        changed['body'] += ' '
        bad_structure = encode_envelope(piece.origin, '{"terminal":["1","0","0","1"],"support":[]}')
        terminal_pole = encode_envelope(piece.origin, '{"terminal":["0","1","1","0"],"support":[[null,null,false,false]]}')
        verify_envelope(bad_structure)
        verify_envelope(terminal_pole)
        for invalid_wire in (json.dumps(changed), bad_structure, terminal_pole):
            with self.subTest(wire=invalid_wire), self.assertRaises(RejectedPiece):
                receive(self.receipts, invalid_wire, 'OLD-A')
            self.assertEqual(self.receipt_count(), 0)
        with self.assertRaises(KeyError):
            issue(self.station, revision + 100)
        receive(self.receipts, piece.wire, 'OLD-A')
        self.assertEqual(self.receipt_count(), 1)
