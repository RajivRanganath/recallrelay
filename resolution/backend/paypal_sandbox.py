"""PayPal SANDBOX refund adapter. Never targets live PayPal; secrets never reach logs, reprs or errors.

Outcome mapping keeps the human-approval flow safe: a definitive refusal is RefundRejected, anything
that leaves the outcome uncertain is RefundUnknown so the case stays pending and can be reconciled
with the same operation ID (sent as PayPal-Request-Id, which makes the refund idempotent).
"""
import base64
import json
import time
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from resolution.backend.envfile import read_secrets
from resolution.backend.paypal import BalanceTooLow, BalanceUnclear, CaptureNotRefundable, OpenDispute, RefundRejected, RefundUnknown

SANDBOX_URL = 'https://api-m.sandbox.paypal.com'
MAX_RESPONSE_BYTES = 65536
SECRET_NAMES = ('PAYPAL_CLIENT_ID', 'PAYPAL_CLIENT_SECRET')
DEFINITIVE_STATUSES = {400, 404, 422}  # PayPal business/validation refusals: no refund was created.


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def load_credentials(env_file=None):
    secrets = read_secrets(SECRET_NAMES, env_file)
    return secrets['PAYPAL_CLIENT_ID'], secrets['PAYPAL_CLIENT_SECRET']


def _minor(amount):
    """'10.00' -> 1000. None unless it is a non-negative amount with at most two decimals."""
    try:
        value = Decimal(str(amount.get('value'))) * 100
    except (InvalidOperation, ValueError):
        return None
    return int(value) if value.is_finite() and value >= 0 and value == value.to_integral_value() else None


def amount_text(amount_minor):
    return f'{amount_minor // 100}.{amount_minor % 100:02d}'


class SandboxPayPal:
    mode = 'sandbox'

    def __init__(self, client_id, client_secret, base_url=SANDBOX_URL, timeout=10):
        parsed = urlsplit(base_url)
        sandbox = parsed.scheme == 'https' and parsed.hostname == 'api-m.sandbox.paypal.com' and not parsed.port
        loopback_test = parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost')  # Local stub servers only.
        if not (sandbox or loopback_test) or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
            raise ValueError('Only the PayPal sandbox (or a loopback test stub) is allowed')
        if not client_id or not client_secret:
            raise ValueError('PayPal sandbox credentials are required')
        self._auth = base64.b64encode(f'{client_id}:{client_secret}'.encode()).decode()
        self.base_url, self.timeout = base_url.rstrip('/'), timeout
        self._token, self._expires = None, 0.0
        self._opener = build_opener(ProxyHandler({}), NoRedirect())

    def __repr__(self):
        return '<SandboxPayPal mode=sandbox>'

    def _send(self, request):
        """Return (status, parsed JSON or None). Raises RefundUnknown on any transport problem."""
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                status, raw = response.status, response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            status, raw = error.code, error.read(MAX_RESPONSE_BYTES + 1)
            error.close()
        except (URLError, TimeoutError, OSError, ValueError):
            raise RefundUnknown('PayPal could not be reached') from None
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RefundUnknown('PayPal response was too large')
        try:
            return status, json.loads(raw) if raw else None
        except ValueError:
            return status, None

    def _bearer(self):
        if self._token and time.monotonic() < self._expires:
            return self._token
        request = Request(self.base_url + '/v1/oauth2/token', data=b'grant_type=client_credentials', method='POST', headers={
            'Authorization': 'Basic ' + self._auth, 'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'})
        status, body = self._send(request)
        token = body.get('access_token') if isinstance(body, dict) else None
        expires = body.get('expires_in') if isinstance(body, dict) else None
        if status != 200 or not isinstance(token, str) or type(expires) is not int:
            raise RefundUnknown('PayPal authentication failed; no refund was requested')  # Nothing sent, safe to retry.
        self._token, self._expires = token, time.monotonic() + max(expires - 60, 0)
        return token

    def refund(self, operation_id, capture_id, amount_minor, currency):
        if currency != 'USD':
            raise RefundRejected('Only USD refunds are supported')
        payload = json.dumps({'amount': {'value': amount_text(amount_minor), 'currency_code': currency}}).encode()
        request = Request(f'{self.base_url}/v2/payments/captures/{quote(capture_id, safe="")}/refund', data=payload, method='POST', headers={
            'Authorization': 'Bearer ' + self._bearer(), 'Content-Type': 'application/json', 'Accept': 'application/json',
            'PayPal-Request-Id': operation_id, 'Prefer': 'return=representation'})
        status, body = self._send(request)
        if status in (200, 201) and isinstance(body, dict) and isinstance(body.get('id'), str):
            outcome = body.get('status')
            if outcome == 'COMPLETED':
                return body['id']
            if outcome in ('FAILED', 'CANCELLED'):
                raise RefundRejected('PayPal did not complete the refund')
            raise RefundUnknown('PayPal reported the refund as pending')  # Includes PENDING and unfamiliar statuses.
        if status in DEFINITIVE_STATUSES:
            raise RefundRejected('PayPal refused the refund')
        if status == 401:
            self._token = None  # Expired or revoked token: fetch a fresh one on the next attempt.
        raise RefundUnknown('PayPal returned an unexpected response')  # 401/403/409/429/5xx: outcome uncertain or retriable.

    def _get(self, path):
        return self._send(Request(self.base_url + path, method='GET', headers={
            'Authorization': 'Bearer ' + self._bearer(), 'Accept': 'application/json'}))

    def check_capture(self, capture_id, amount_minor, currency):
        """Read-only checks before approval: payment state, refunded balance and open disputes.

        Raises CaptureNotRefundable (case goes to manual handling) when PayPal says no, and RefundUnknown
        when PayPal cannot be read (approval is blocked and nothing is sent).
        """
        status, body = self._get(f'/v2/payments/captures/{quote(capture_id, safe="")}')
        if status == 404:
            raise CaptureNotRefundable('PayPal does not know this payment')
        if status != 200 or not isinstance(body, dict):
            raise RefundUnknown('Payment could not be checked')
        amount = body.get('amount') if isinstance(body.get('amount'), dict) else {}
        total_minor = _minor(amount)
        if total_minor is None:
            raise CaptureNotRefundable('PayPal returned an unreadable payment amount')
        if body.get('status') not in ('COMPLETED', 'PARTIALLY_REFUNDED'):
            raise CaptureNotRefundable('PayPal says this payment is not in a refundable state')
        if amount.get('currency_code') != currency or amount_minor > total_minor:
            raise CaptureNotRefundable('The approved amount does not fit this payment')
        related = body.get('supplementary_data', {}).get('related_ids') if isinstance(body.get('supplementary_data'), dict) else None
        order_id = related.get('order_id') if isinstance(related, dict) else None
        if not isinstance(order_id, str) or not order_id:
            raise BalanceUnclear('No order is linked to this payment')
        if amount_minor > total_minor - self._refunded_minor(order_id, capture_id, currency):
            raise BalanceTooLow('Less is left to refund than the approved amount')
        self._check_disputes(capture_id)

    def _refunded_minor(self, order_id, capture_id, currency):
        """Total already refunded on this payment, read from its order. Anything unclear counts as unclear."""
        status, body = self._get(f'/v2/checkout/orders/{quote(order_id, safe="")}')
        if status != 200 or not isinstance(body, dict):
            raise RefundUnknown('Refund history could not be read')
        captures, refunds = [], []
        for unit in body.get('purchase_units') if isinstance(body.get('purchase_units'), list) else []:
            payments = unit.get('payments') if isinstance(unit, dict) and isinstance(unit.get('payments'), dict) else {}
            captures += payments.get('captures') if isinstance(payments.get('captures'), list) else []
            refunds += payments.get('refunds') if isinstance(payments.get('refunds'), list) else []
        if len(captures) != 1 or not isinstance(captures[0], dict) or captures[0].get('id') != capture_id:
            raise BalanceUnclear('The order does not hold exactly this one payment')  # Refunds could not be attributed.
        total = 0
        for refund in refunds:
            if not isinstance(refund, dict):
                raise BalanceUnclear('Unreadable refund entry')
            if refund.get('status') in ('FAILED', 'CANCELLED'):
                continue  # Only refunds that did not happen are ignored; unfamiliar statuses count as refunded.
            amount = refund.get('amount') if isinstance(refund.get('amount'), dict) else {}
            minor = _minor(amount)
            if minor is None or amount.get('currency_code') != currency:
                raise BalanceUnclear('Unreadable refund amount')
            total += minor
        return total

    def _check_disputes(self, capture_id):
        status, body = self._get('/v1/customer/disputes?disputed_transaction_id=' + quote(capture_id, safe=''))
        items = body.get('items') if isinstance(body, dict) else None
        if status != 200 or not isinstance(items, list):
            raise RefundUnknown('Disputes could not be checked')  # Fail closed: no answer is not "no dispute".
        for item in items:
            if not isinstance(item, dict) or item.get('status') != 'RESOLVED':
                raise OpenDispute('PayPal lists a dispute on this payment that is not resolved')

    def verify_webhook(self, headers, raw, webhook_id):
        """Ask PayPal whether a delivered event is genuine. True only on an explicit SUCCESS.

        `headers` has lowercase names. PayPal's own API checks the signature; nothing is fetched from the
        event's cert URL by us. Raises RefundUnknown if PayPal cannot be reached.
        """
        try:
            event = json.loads(raw)
        except ValueError:
            return False
        names = {'auth_algo': 'paypal-auth-algo', 'cert_url': 'paypal-cert-url', 'transmission_id': 'paypal-transmission-id',
                 'transmission_sig': 'paypal-transmission-sig', 'transmission_time': 'paypal-transmission-time'}
        fields = {key: headers.get(header) for key, header in names.items()}
        if not webhook_id or not isinstance(event, dict) or not all(isinstance(v, str) and v for v in fields.values()):
            return False
        payload = json.dumps(dict(fields, webhook_id=webhook_id, webhook_event=event)).encode()
        status, body = self._send(Request(f'{self.base_url}/v1/notifications/verify-webhook-signature', data=payload, method='POST', headers={
            'Authorization': 'Bearer ' + self._bearer(), 'Content-Type': 'application/json', 'Accept': 'application/json'}))
        return status == 200 and isinstance(body, dict) and body.get('verification_status') == 'SUCCESS'

    def get_refund(self, refund_id):
        """Read-back for verification only. Never creates or changes anything."""
        request = Request(f'{self.base_url}/v2/payments/refunds/{quote(refund_id, safe="")}', method='GET', headers={
            'Authorization': 'Bearer ' + self._bearer(), 'Accept': 'application/json'})
        status, body = self._send(request)
        if status != 200 or not isinstance(body, dict):
            raise RefundUnknown('Refund could not be read back')
        return {key: body.get(key) for key in ('id', 'status', 'amount', 'create_time')}
