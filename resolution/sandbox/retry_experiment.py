"""Retry experiment against the PayPal SANDBOX: a partial refund whose response is "dropped", then retried.

    python -m resolution.sandbox.retry_experiment CASE_FILE --paypal-env PATH_TO_ENV_FILE

CASE_FILE is a file made by `resolution.sandbox.make_capture` (it holds a real sandbox capture ID). The script
sends one partial refund (default 10.00 USD) with a fixed PayPal-Request-Id, throws the answer away as if the
connection had dropped, sends the same request again, and reads the refund back from PayPal. If PayPal treats the
retry as the same request, both calls return the same refund ID and the read-back shows one refund of the partial
amount. It creates a real sandbox refund; use a payment you do not mind refunding. No live PayPal is reachable.
"""
import argparse
import json
from pathlib import Path
import uuid

from resolution.backend.paypal import RefundRejected, RefundUnknown
from resolution.backend.paypal_sandbox import SandboxPayPal, amount_text, load_credentials


def run(adapter, capture_id, amount_minor, request_id, currency='USD'):
    """Return a dict of what was observed. Never raises for PayPal outcomes; they are recorded."""
    seen = {'request_id': request_id, 'capture_id': capture_id, 'amount': amount_text(amount_minor)}
    try:
        adapter.check_capture(capture_id, amount_minor, currency)
        first = adapter.refund(request_id, capture_id, amount_minor, currency)  # The "dropped" answer: kept only to compare.
        seen['first_call'] = 'refund created; answer discarded to simulate a dropped response'
        second = adapter.refund(request_id, capture_id, amount_minor, currency)
        found = adapter.get_refund(second)
    except (RefundRejected, RefundUnknown) as error:
        seen['error'] = f'{type(error).__name__}: {error}'
        seen['passed'] = False
        return seen
    amount = found.get('amount') or {}
    seen.update(first_refund_id=first, retry_refund_id=second, read_back=found,
                same_refund_id=first == second,
                read_back_matches=(found.get('status') == 'COMPLETED' and amount.get('value') == amount_text(amount_minor)
                                   and amount.get('currency_code') == currency))
    seen['passed'] = seen['same_refund_id'] and seen['read_back_matches']
    return seen


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('case_file', type=Path)
    parser.add_argument('--paypal-env', help='Env file with PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET (read, never executed)')
    parser.add_argument('--amount-minor', type=int, default=1000, help='Partial amount in cents (default 1000 = 10.00 USD)')
    parser.add_argument('--request-id', default=None, help='Fixed PayPal-Request-Id (default: a new random one)')
    parser.add_argument('--output', type=Path, help='Optional report file; never overwrites an existing file')
    args = parser.parse_args()
    if args.amount_minor <= 0:
        parser.error('--amount-minor must be positive')
    try:
        capture_id = json.loads(args.case_file.read_text())['order']['capture_id']
        adapter = SandboxPayPal(*load_credentials(args.paypal_env))
    except (OSError, ValueError, KeyError, TypeError):
        parser.error('Could not read the case file or the PayPal sandbox credentials')
    if not isinstance(capture_id, str) or capture_id.startswith('capture-demo'):
        parser.error('The case file does not hold a real sandbox capture ID')
    seen = run(adapter, capture_id, args.amount_minor, args.request_id or 'retry-' + uuid.uuid4().hex[:24])
    text = json.dumps(seen, indent=2)
    print(text)
    if args.output:
        with open(args.output, 'x') as handle:
            handle.write(text + '\n')
    print('RESULT:', 'PASSED' if seen['passed'] else 'DID NOT PASS (record exactly what printed)')
    raise SystemExit(0 if seen['passed'] else 1)


if __name__ == '__main__':
    main()
