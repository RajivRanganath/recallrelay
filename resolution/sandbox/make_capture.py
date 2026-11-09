"""Create ONE real PayPal-SANDBOX captured payment and write a resolution case that points at it.

You run this yourself with your sandbox credentials in an existing env file. A sandbox buyer approves the
order in the browser, so no password is ever typed into or by this script. Sandbox only: the adapter
refuses any non-sandbox host. The assessment inside the written case is the synthetic contract fixture,
not a real evidence assessment.

    python -m resolution.sandbox.make_capture --paypal-env PATH_TO_ENV_FILE
"""
import argparse
import copy
import json
from pathlib import Path
import uuid

from resolution.backend.paypal import RefundUnknown
from resolution.backend.paypal_sandbox import SandboxPayPal, amount_text, load_credentials
from resolution.backend.validation import ROOT, validate_contract


def call(adapter, method, path, body=None):
    from urllib.request import Request
    headers = {'Authorization': 'Bearer ' + adapter._bearer(), 'Accept': 'application/json'}
    if body is not None:
        headers.update({'Content-Type': 'application/json', 'PayPal-Request-Id': str(uuid.uuid4())})
    request = Request(adapter.base_url + path, data=json.dumps(body).encode() if body is not None else None, method=method, headers=headers)
    status, data = adapter._send(request)
    if status not in (200, 201) or not isinstance(data, dict):
        raise SystemExit(f'PayPal returned HTTP {status} for {method} {path}; nothing was written.')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--paypal-env', help='Env file with PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET (read, never executed)')
    parser.add_argument('--case-id', default='case-sandbox-1')
    parser.add_argument('--amount-minor', type=int, default=4000)
    parser.add_argument('--output', type=Path, default=ROOT / 'resolution' / '.local' / 'sandbox-case.json')
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error('Choose a new --output path; refusing to overwrite an existing file')
    try:
        adapter = SandboxPayPal(*load_credentials(args.paypal_env))
    except (OSError, ValueError):
        parser.error('Could not load PayPal sandbox credentials')
    try:
        order = call(adapter, 'POST', '/v2/checkout/orders', {
            'intent': 'CAPTURE',
            'purchase_units': [{'amount': {'currency_code': 'USD', 'value': amount_text(args.amount_minor)}}],
            'payment_source': {'paypal': {'experience_context': {
                'return_url': 'https://example.com/return', 'cancel_url': 'https://example.com/cancel', 'user_action': 'PAY_NOW'}}}})
        link = next((item['href'] for item in order.get('links', []) if item.get('rel') in ('payer-action', 'approve')), None)
        if not link:
            raise SystemExit('PayPal returned no approval link; nothing was written.')
        print(f'\nOpen this link, log in with a SANDBOX BUYER account and approve the payment:\n  {link}\n')
        input('Press Enter here after you approved it (you may land on example.com, that is fine)... ')
        captured = call(adapter, 'POST', f"/v2/checkout/orders/{order['id']}/capture", {})
        capture = captured['purchase_units'][0]['payments']['captures'][0]
        if capture.get('status') != 'COMPLETED':
            raise SystemExit(f"Capture status was {capture.get('status')}; nothing was written.")
    except RefundUnknown:
        raise SystemExit('PayPal could not be reached or authenticated; nothing was written.')
    request = json.loads((ROOT / 'contracts' / 'fixtures' / 'resolution-request.json').read_text())
    request = copy.deepcopy(request)
    request['order'].update(case_id=args.case_id, order_id=order['id'], capture_id=capture['id'], paid_minor=args.amount_minor)
    request['assessment'].update(case_id=args.case_id, assessment_id=f'assessment-{args.case_id}')
    validate_contract('resolution-request', request)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(request, indent=2) + '\n')
    print(f"Captured sandbox payment {capture['id']}. Case written to {args.output}")
    print('Next: start the server with --paypal sandbox, POST this file to /v1/resolutions, confirm the remedy in the UI, approve, then verify with resolution.sandbox.verify_refund.')


if __name__ == '__main__':
    main()
