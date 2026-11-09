"""Read a refund back from the PayPal SANDBOX to prove it exists. Read-only; creates and changes nothing.

    python -m resolution.sandbox.verify_refund REFUND_ID --paypal-env PATH_TO_ENV_FILE
"""
import argparse
import json

from resolution.backend.paypal import RefundUnknown
from resolution.backend.paypal_sandbox import SandboxPayPal, load_credentials


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('refund_id')
    parser.add_argument('--paypal-env', help='Env file with PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET (read, never executed)')
    args = parser.parse_args()
    try:
        adapter = SandboxPayPal(*load_credentials(args.paypal_env))
    except (OSError, ValueError):
        parser.error('Could not load PayPal sandbox credentials')
    try:
        print(json.dumps(adapter.get_refund(args.refund_id), indent=2))
    except RefundUnknown:
        raise SystemExit('Could not read the refund back from the PayPal sandbox.')


if __name__ == '__main__':
    main()
