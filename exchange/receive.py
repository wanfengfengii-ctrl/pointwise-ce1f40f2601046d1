from exchange.calibration_body import decode_body
from exchange.envelope import verify_envelope
from exchange.receipts import ReceiptStore


class RejectedPiece(ValueError):
    """The received calibration evidence is inadmissible."""


def receive(store: ReceiptStore, wire: str, expected_instrument: str) -> int:
    try:
        envelope = verify_envelope(wire)
        if not isinstance(expected_instrument, str) or envelope.origin.instrument_id != expected_instrument:
            raise ValueError('instrument does not match the expected identity')
        body = decode_body(envelope.body)
    except (ValueError, RecursionError) as error:
        raise RejectedPiece(str(error)) from error
    return store.record(envelope, body)
