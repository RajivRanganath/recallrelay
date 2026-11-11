"""Bound local handler concurrency and time spent receiving a request.

These controls serve the synthetic loopback demo, not a production HTTP service.
"""
import io
import math
import socket
import threading
import time
from http.server import HTTPServer


class BoundedHTTPServer(HTTPServer):
    def __init__(self, address, handler, *, max_handlers=8, request_timeout=10):
        if type(max_handlers) is not int or max_handlers < 1:
            raise ValueError('max_handlers must be a positive integer')
        if not math.isfinite(request_timeout) or request_timeout <= 0:
            raise ValueError('request_timeout must be finite and positive')
        self.request_timeout = request_timeout
        self._slots = threading.BoundedSemaphore(max_handlers)
        self._workers = set()
        super().__init__(address, handler)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            # No worker or application work for excess connections. Keep this
            # best-effort reply brief so a non-reading peer cannot stall accept.
            body = b'{"error":"Evidence server is busy; try again later"}'
            raw = (b'HTTP/1.0 503 Service Unavailable\r\n'
                   b'Content-Type: application/json\r\n'
                   b'Cache-Control: no-store\r\n'
                   b'X-Content-Type-Options: nosniff\r\n'
                   b'Connection: close\r\nContent-Length: '
                   + str(len(body)).encode('ascii') + b'\r\n\r\n' + body)
            try:
                request.settimeout(.05)
                request.sendall(raw)
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        worker = threading.Thread(target=self.process_request_thread,
                                  args=(request, client_address), daemon=False)
        try:
            worker.start()
        except BaseException:
            self._slots.release()
            raise
        # Only successfully started workers may be joined. The accept loop is
        # the sole writer; call server_close after stopping that loop as usual.
        self._workers = {thread for thread in self._workers if thread.is_alive()}
        self._workers.add(worker)

    def process_request_thread(self, request, client_address):
        try:
            try:
                self.finish_request(request, client_address)
            except Exception:
                self.handle_error(request, client_address)
        finally:
            try:
                self.shutdown_request(request)
            finally:
                self._slots.release()

    def server_close(self):
        super().server_close()
        for worker in self._workers:
            worker.join()
        self._workers.clear()


class IntakeDeadline:
    """Interrupt socket reads after a total receive budget, including trickles.

    Completion cancels the watchdog before JSON/AI/storage processing. It never
    interrupts business logic or rolls back an operation after input is accepted.
    """
    def __init__(self, connection, timeout):
        self._connection = connection
        self._socket_timeout = connection.gettimeout()
        self._end = time.monotonic() + timeout
        self._lock = threading.Lock()
        self._done = False
        self._expired = False
        self._timer = threading.Timer(timeout, self._expire)
        self._timer.daemon = True
        self._timer.start()

    def _expire(self):
        with self._lock:
            if self._done:
                return
            self._expired = True
            try:
                self._connection.shutdown(socket.SHUT_RD)
            except OSError:
                pass

    def expired(self):
        with self._lock:
            return self._expired or (not self._done and time.monotonic() >= self._end)

    def read_timeout(self):
        with self._lock:
            remaining = max(0, self._end - time.monotonic())
            if self._socket_timeout is not None:
                remaining = min(remaining, self._socket_timeout)
            return remaining

    def complete(self):
        with self._lock:
            self._expired = self._expired or (not self._done and time.monotonic() >= self._end)
            self._done = True
            self._timer.cancel()
            self._connection.settimeout(self._socket_timeout)
            return not self._expired

    def close(self):
        self.complete()
        self._timer.join()


class DeadlineReader(io.RawIOBase):
    """Recompute the total budget before each recv, including buffered readlines.

    Windows shutdown(SHUT_RD) alone need not wake an already blocked recv. A
    per-recv timeout supplies the same deadline without relying on that wakeup.
    """
    def __init__(self, connection, deadline):
        super().__init__()
        self.connection, self.deadline = connection, deadline

    def readable(self):
        return True

    def readinto(self, buffer):
        timeout = self.deadline.read_timeout()
        if timeout <= 0:
            return 0
        self.connection.settimeout(timeout)
        try:
            return self.connection.recv_into(buffer)
        except OSError:
            if self.deadline.expired():
                return 0
            raise
