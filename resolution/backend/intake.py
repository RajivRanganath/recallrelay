"""Bounds on how long and how many connections the merchant server will serve while a request is being received.

`socket.settimeout` limits each wait for data, not the whole request: a sender that trickles one byte every few
seconds can hold a handler thread open indefinitely. These helpers add a total receive budget per request and a
cap on simultaneous connections. They matter most while a temporary public host is enabled
(docs/vismaya/WEBHOOK-EXCEPTION.md), and they apply to every connection.
"""
import io
from http.server import ThreadingHTTPServer
import threading
import time


class ReceiveDeadline:
    """One total time budget for receiving a whole request (request line, headers and body)."""

    def __init__(self, connection, seconds, socket_timeout):
        self.connection, self.socket_timeout = connection, socket_timeout
        self._end = time.monotonic() + seconds
        self._done = False
        # Set for good once the budget cut off a read. `complete()` does not clear it: an end of stream that came
        # from the budget is not a real end of the request, and the request must not be treated as received.
        self.timed_out = False

    def remaining(self):
        return max(0.0, self._end - time.monotonic())

    def expired(self):
        return not self._done and self.remaining() <= 0

    def complete(self):
        """Receiving is over: restore the normal socket timeout so the reply is written with it."""
        self._done = True
        self.connection.settimeout(self.socket_timeout)


class DeadlineReader(io.RawIOBase):
    """Recomputes the remaining budget before every recv, so the total, not each wait, is bounded.

    Windows' shutdown() need not wake a recv that is already blocked, so a per-recv timeout is used instead.
    When the budget is spent the reader reports end of stream, like a closed connection.
    """

    def __init__(self, connection, deadline):
        super().__init__()
        self.connection, self.deadline = connection, deadline

    def readable(self):
        return True

    def readinto(self, buffer):
        timeout = self.deadline.remaining()
        if timeout <= 0:
            self.deadline.timed_out = True
            return 0
        # True when the total budget, not the ordinary per-wait timeout, is what limits this wait.
        limited_by_budget = self.deadline.socket_timeout is None or timeout <= self.deadline.socket_timeout
        if self.deadline.socket_timeout is not None:
            timeout = min(timeout, self.deadline.socket_timeout)
        self.connection.settimeout(timeout)
        try:
            return self.connection.recv_into(buffer)
        except OSError as error:
            # The socket timer can fire a few milliseconds before the monotonic clock says the budget is spent
            # (Windows timer granularity). A timeout that the budget itself caused is budget expiry either way.
            if self.deadline.expired() or (limited_by_budget and isinstance(error, TimeoutError)):
                self.deadline.timed_out = True
                return 0
            raise


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    """At most `max_connections` handler threads at once; further connections are closed immediately.

    The refused connection is closed without a reply. A reply would be unreliable: closing a socket with
    unread request data resets the connection, and on Windows the reset discards the reply. Callers
    (a browser, the evidence service, PayPal's retries) simply try again.
    """

    def __init__(self, address, handler, max_connections=32):
        super().__init__(address, handler)
        self._slots = threading.BoundedSemaphore(max_connections)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()
