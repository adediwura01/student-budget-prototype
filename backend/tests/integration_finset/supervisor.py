"""Owned-worker hard stop and private, acknowledged secret registration.

The worker uses open_control(int(number)), receive_spec(timeout=5), then
secret_registration(values, timeout=5) BEFORE using credentials. Collection
and non-emitting probes register []. The parent retains all authorization and
metadata gates; this module neither authorizes database access nor verifies
rollback. Probe workers must preload the parent's deny-all unit guard.

Only the owned worker is killed. It must not spawn descendants. The wall-clock
bound is run_timeout + cleanup_timeout, subject to healthy OS process creation,
pipe operations and termination. No communicate() or unbounded join is used.
"""

from collections import deque
from dataclasses import dataclass
import json
import math
import os
import signal
import stat
import subprocess
import sys
import threading
import time

from . import policy as cwdpolicy
from .output import MAX_SECRETS, SECRET_LIMIT, SecretFilter


CONTROL_LIMIT = SECRET_LIMIT
SPEC_LIMIT = 8192
MAX_REGISTRATIONS = 32
DEFAULT_OUTPUT_LIMIT = 1048576
_ACK_LIMIT = 64
_ACK = b'{"type":"ack"}\n'
_PAUSE = 0.01
_IDLE = threading.Event()
_SPAWN_LOCK = threading.Lock()
PROBE_NAMES = frozenset({"hang", "emit", "bad_control", "oversize"})


@dataclass(frozen=True)
class Result:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    terminated: bool


class ControlError(RuntimeError):
    """A private protocol error containing no payload or exception details."""


def _duration(value, *, zero=False):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or value > threading.TIMEOUT_MAX or value < 0 or (not zero and value == 0)):
        raise ControlError("Invalid supervisor deadline.")
    return float(value)


def _remaining(deadline):
    return max(0.0, deadline - time.monotonic())


def _spec(spec):
    """Structural allowlist only; the launcher approves selectors and opt-in."""
    if type(spec) is not dict or type(spec.get("mode")) is not str:
        raise ControlError("Invalid nonsecret worker specification.")
    mode = spec["mode"]
    if mode == "probe":
        if (set(spec) != {"mode", "probe"} or type(spec["probe"]) is not str
                or spec["probe"] not in PROBE_NAMES):
            raise ControlError("Invalid nonsecret probe specification.")
        normalized = dict(spec)
    elif mode in {"live", "collect"}:
        if set(spec) - {"mode", "opted_in", "k", "m", "q", "v"} or spec.get("opted_in") is not True:
            raise ControlError("Unapproved worker option.")
        normalized = {"mode": mode, "opted_in": True, "k": spec.get("k", ""),
                      "m": spec.get("m", "integration and finset_integration and not finset_committed"),
                      "q": spec.get("q", False), "v": spec.get("v", 0)}
        for key in ("k", "m"):
            text = normalized[key]
            if (type(text) is not str or len(text) > 2048
                    or any(ord(char) < 32 or ord(char) == 127 for char in text)):
                raise ControlError("Invalid nonsecret selector.")
        if (type(normalized["q"]) is not bool or type(normalized["v"]) is not int
                or not 0 <= normalized["v"] <= 3):
            raise ControlError("Invalid approved reporting option.")
    else:
        raise ControlError("Invalid worker mode.")
    payload = (json.dumps(normalized, ensure_ascii=True, separators=(",", ":")) + "\n").encode("ascii")
    if len(payload) > SPEC_LIMIT:
        raise ControlError("Worker specification exceeds its private limit.")
    return normalized, payload


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ControlError("Duplicate private protocol field.")
        result[key] = value
    return result


def _constant(value):
    raise ControlError("Invalid private JSON constant.")


def _json(line):
    __tracebackhide__ = True
    try:
        value = json.loads(line.decode("utf-8"), object_pairs_hook=_object, parse_constant=_constant)
        if type(value) is not dict:
            raise ValueError
        return value
    except Exception:
        raise ControlError("Malformed private control protocol.") from None


def _environment():
    # Do not inherit credentials, Python hooks, pytest options, proxies or PATH.
    result = {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1",
              "PYTHONIOENCODING": "utf-8", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    if os.name == "nt" and os.environ.get("SystemRoot"):
        result["SystemRoot"] = os.environ["SystemRoot"]
    return result


def _spawn(deadline):
    read_fd, write_fd = os.pipe()
    stream = None
    acquired = False
    handle = None
    try:
        stream = os.fdopen(read_fd, "rb", buffering=0)
        acquired = _SPAWN_LOCK.acquire(timeout=_remaining(deadline))
        if not acquired or not _remaining(deadline):
            raise ControlError("Worker creation deadline exceeded.")
        kwargs = dict(cwd=str(cwdpolicy.BACKEND), stdin=subprocess.PIPE,
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
                      close_fds=True, shell=False, env=_environment())
        if os.name == "nt":
            import msvcrt

            handle = msvcrt.get_osfhandle(write_fd)
            os.set_handle_inheritable(handle, True)
            startup = subprocess.STARTUPINFO()
            startup.lpAttributeList = {"handle_list": [handle]}
            kwargs["startupinfo"] = startup
            number = handle
        else:
            os.set_inheritable(write_fd, True)
            kwargs["pass_fds"] = (write_fd,)
            number = write_fd
        process = subprocess.Popen(
            [sys.executable, "-u", "-B", "-m", "tests.integration_finset.worker",
             "--control", str(number)], **kwargs
        )
        return process, stream
    except Exception:
        try:
            if stream is not None:
                stream.close()
            else:
                os.close(read_fd)
        except OSError:
            pass
        raise
    finally:
        try:
            if handle is not None:
                os.set_handle_inheritable(handle, False)
            else:
                os.set_inheritable(write_fd, False)
        except OSError:
            pass
        try:
            os.close(write_fd)
        except OSError:
            pass
        finally:
            if acquired:
                _SPAWN_LOCK.release()


class _PipeReader:
    """Single-owner, nonblocking reads, including Windows anonymous pipes."""

    def __init__(self, stream):
        self.stream = None if type(stream) is int else stream
        self.fd = stream if self.stream is None else stream.fileno()
        self.eof = False
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            import msvcrt

            self._ctypes = ctypes
            self._available = wintypes.DWORD()
            self._handle = msvcrt.get_osfhandle(self.fd)
            self._peek = ctypes.WinDLL("kernel32", use_last_error=True).PeekNamedPipe
            self._peek.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                                   wintypes.LPDWORD, wintypes.LPDWORD, wintypes.LPDWORD]
            self._peek.restype = wintypes.BOOL
        else:
            os.set_blocking(self.fd, False)

    def read(self, limit=65536):
        if self.eof:
            return b""
        if os.name == "nt":
            if not self._peek(self._handle, None, 0, None,
                              self._ctypes.byref(self._available), None):
                if self._ctypes.get_last_error() in {109, 232, 233}:
                    self.eof = True
                    return b""
                raise ControlError("Private pipe read failed.")
            if not self._available.value:
                return None
            limit = min(limit, self._available.value)
        try:
            chunk = os.read(self.fd, limit)
        except (BlockingIOError, InterruptedError):
            return None
        if not chunk:
            self.eof = True
        return chunk


class _Writer:
    """Bounded write queue; a Windows blocked WriteFile never blocks the caller.

    The daemon owns and closes its unbuffered stream. Killing the sole child
    releases a blocked pipe write on a healthy OS; stop() never joins forever.
    """

    def __init__(self, stream):
        self.stream = stream
        self.fd = stream.fileno()
        if os.name != "nt":
            os.set_blocking(self.fd, False)
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._queue = deque()
        self._total = self._ticket = self._completed = 0
        self._failed = self._stopped = False
        self._thread = threading.Thread(target=self._run, daemon=True, name="finset-private-write")
        self._thread.start()

    def send(self, payload):
        with self._lock:
            if (self._failed or self._stopped or type(payload) is not bytes
                    or self._total + len(payload) > CONTROL_LIMIT + SPEC_LIMIT
                    or len(self._queue) >= MAX_REGISTRATIONS + 1):
                raise ControlError("Private write queue is unavailable or exceeds its limit.")
            self._total += len(payload)
            self._ticket += 1
            self._queue.append((self._ticket, payload))
            self._ready.set()
            return self._ticket

    @property
    def failed(self):
        with self._lock:
            return self._failed

    def finished(self, ticket):
        with self._lock:
            return self._completed >= ticket

    def _run(self):
        try:
            while True:
                with self._lock:
                    if self._stopped:
                        return
                    item = self._queue.popleft() if self._queue else None
                if item is None:
                    self._ready.wait(0.05)
                    self._ready.clear()
                    continue
                ticket, payload = item
                offset = 0
                while offset < len(payload):
                    with self._lock:
                        if self._stopped:
                            return
                    try:
                        count = os.write(self.fd, memoryview(payload)[offset:])
                    except BlockingIOError:
                        self._ready.wait(_PAUSE)
                        self._ready.clear()
                        continue
                    except InterruptedError:
                        continue
                    if count <= 0:
                        raise ControlError("Private pipe write failed.")
                    offset += count
                with self._lock:
                    self._completed = ticket
        except Exception:
            with self._lock:
                self._failed = True
                self._queue.clear()
        finally:
            try:
                self.stream.close()
            except OSError:
                with self._lock:
                    self._failed = True

    def stop(self, timeout):
        with self._lock:
            self._stopped = True
            self._queue.clear()
            self._ready.set()
        self._thread.join(timeout=max(0.0, timeout))
        return not self._thread.is_alive()


class ControlClient:
    """Worker-side private pipe owner. stdin_fd is injectable for synthetic tests."""

    def __init__(self, control_fd, *, stdin_fd=0):
        try:
            if (type(control_fd) is not int or control_fd < 3
                    or not stat.S_ISFIFO(os.fstat(control_fd).st_mode)):
                raise ValueError
            os.set_inheritable(control_fd, False)
        except Exception:
            raise ControlError("Private control descriptor is not an owned pipe.") from None
        stream = os.fdopen(control_fd, "wb", buffering=0)
        try:
            self._writer = _Writer(stream)
        except Exception:
            stream.close()
            raise ControlError("Private control writer is unavailable.") from None
        try:
            self._input = _PipeReader(stdin_fd)
        except Exception:
            self._writer.stop(0)
            raise ControlError("Worker stdin pipe is unavailable.") from None
        self._pending = bytearray()
        self._input_total = self._control_total = self._registrations = 0
        self._received = self._closed = False
        self._lock = threading.Lock()

    def _line(self, deadline, limit):
        while True:
            if self._closed or not _remaining(deadline):
                raise ControlError("Private acknowledgement deadline exceeded.")
            index = self._pending.find(b"\n")
            if index >= 0:
                if index + 1 > limit:
                    raise ControlError("Private stdin frame exceeds its limit.")
                line = bytes(self._pending[:index])
                del self._pending[:index + 1]
                return line
            if len(self._pending) >= limit:
                raise ControlError("Private stdin frame exceeds its limit.")
            chunk = self._input.read(min(4096, limit - len(self._pending)))
            if chunk is None:
                _IDLE.wait(min(_PAUSE, _remaining(deadline)))
                continue
            if not chunk:
                raise ControlError("Private stdin closed before acknowledgement.")
            self._input_total += len(chunk)
            if self._input_total > SPEC_LIMIT + MAX_REGISTRATIONS * _ACK_LIMIT:
                raise ControlError("Private stdin exceeds its lifetime limit.")
            self._pending.extend(chunk)

    def receive_spec(self, *, timeout=5):
        __tracebackhide__ = True
        deadline = time.monotonic() + _duration(timeout)
        if not self._lock.acquire(timeout=_remaining(deadline)):
            raise ControlError("Worker specification deadline exceeded.")
        try:
            if self._closed or self._received:
                raise ControlError("Worker specification cannot be reused.")
            spec, _ = _spec(_json(self._line(deadline, SPEC_LIMIT)))
            self._received = True
            return spec
        except Exception:
            self.close(timeout=0)
            raise ControlError("Initial worker specification is invalid or unavailable.") from None
        finally:
            self._lock.release()

    def secret_registration(self, values, *, timeout=5):
        __tracebackhide__ = True
        deadline = time.monotonic() + _duration(timeout)
        if not self._lock.acquire(timeout=_remaining(deadline)):
            raise ControlError("Private secret registration deadline exceeded.")
        try:
            if (self._closed or not self._received or type(values) not in (list, tuple)
                    or len(values) > MAX_SECRETS
                    or any(type(value) is not str or not value or len(value) > SECRET_LIMIT for value in values)
                    or sum(len(value.encode("utf-8")) for value in values) > SECRET_LIMIT):
                raise ControlError("Invalid private secret registration.")
            payload = (json.dumps({"type": "secrets", "values": list(values)},
                                  ensure_ascii=True, separators=(",", ":")) + "\n").encode("ascii")
            self._control_total += len(payload)
            self._registrations += 1
            if self._control_total > CONTROL_LIMIT or self._registrations > MAX_REGISTRATIONS:
                raise ControlError("Private registration exceeds its lifetime limit.")
            ticket = self._writer.send(payload)
            while not self._writer.finished(ticket):
                if self._writer.failed or not _remaining(deadline):
                    raise ControlError("Private registration write was not completed.")
                _IDLE.wait(min(_PAUSE, _remaining(deadline)))
            if (_json(self._line(deadline, _ACK_LIMIT)) != {"type": "ack"}
                    or self._closed or self._writer.failed):
                raise ControlError("Invalid private acknowledgement.")
        except Exception:
            self.close(timeout=0)
            raise ControlError("Private secret registration was not acknowledged; execution must abort.") from None
        finally:
            self._lock.release()

    def fileno(self):
        """Private write descriptor, used only by deliberately malformed probes."""
        if self._closed:
            raise ControlError("Private control channel is closed.")
        return self._writer.fd

    def close(self, *, timeout=0.1):
        timeout = _duration(timeout, zero=True)
        self._closed = True
        self._pending.clear()
        return self._writer.stop(timeout)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def open_control(number):
    """Adopt --control's POSIX write fd or Windows inherited numeric HANDLE."""
    __tracebackhide__ = True
    fd = None
    adopted = False
    try:
        if type(number) is not int or number < 3:
            raise ValueError
        if os.name == "nt":
            import msvcrt

            if number in {msvcrt.get_osfhandle(fd) for fd in (0, 1, 2)}:
                raise ValueError
            fd = msvcrt.open_osfhandle(number, os.O_WRONLY | os.O_BINARY)
        else:
            fd = number
        if not stat.S_ISFIFO(os.fstat(fd).st_mode):
            raise ValueError
        os.set_inheritable(fd, False)
        adopted = True
        return ControlClient(fd)
    except Exception:
        if fd is not None and not adopted:
            try:
                os.close(fd)
            except OSError:
                pass
        raise ControlError("Private worker control pipe is unavailable.") from None


def _supervise(spec: dict, *, run_timeout=120, cleanup_timeout=5,
               output_limit=DEFAULT_OUTPUT_LIMIT, interrupted=None) -> Result:
    """Return only filtered complete output, or suppress both channels on abort.

    output_limit bounds combined raw and returned child output, not the fixed
    supervisor diagnostic. terminated means an owned kill was requested AND
    child exit was confirmed. Nonzero child status is retained, including a
    signal status; otherwise abort uses 70 (124 for the run deadline).
    """
    __tracebackhide__ = True
    start = time.monotonic()
    try:
        run_timeout = _duration(run_timeout)
        cleanup_timeout = _duration(cleanup_timeout, zero=True)
        if type(output_limit) is not int or output_limit <= 0:
            raise ValueError
        _, payload = _spec(spec)
    except Exception:
        return Result(4, "", "Invalid nonsecret supervisor request; execution was not started.\n", False, False)
    run_deadline = start + run_timeout
    final_deadline = run_deadline + cleanup_timeout
    cleanup_deadline = None
    process = control_stream = writer = None
    readers = {}
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    pending = bytearray()
    registry = SecretFilter()
    output_size = control_size = registrations = last_ack = 0
    exited = timed_out = kill_requested = False
    problem = None
    filtered_stdout = filtered_stderr = ""
    try:
        process, control_stream = _spawn(run_deadline)
        writer = _Writer(process.stdin)
        initial_ticket = writer.send(payload)
        for name, stream in (("stdout", process.stdout), ("stderr", process.stderr),
                             ("control", control_stream)):
            readers[name] = _PipeReader(stream)
        while problem is None:
            if interrupted is not None and interrupted.is_set():
                problem = "Worker supervision was interrupted"
                break
            deadline = cleanup_deadline if exited else run_deadline
            if not _remaining(deadline):
                timed_out = not exited
                problem = "Worker hard deadline exceeded" if timed_out else "Worker output drain was not completed"
                break
            for name, reader in readers.items():
                for _ in range(8):
                    if not _remaining(deadline):
                        break
                    chunk = reader.read()
                    if chunk is None or not chunk:
                        break
                    if name != "control":
                        output_size += len(chunk)
                        if output_size > output_limit:
                            problem = "Worker output exceeded its limit"
                            break
                        buffers[name].extend(chunk)
                        continue
                    control_size += len(chunk)
                    if control_size > CONTROL_LIMIT:
                        problem = "Private control protocol exceeded its limit"
                        break
                    pending.extend(chunk)
                    while b"\n" in pending:
                        if not _remaining(deadline):
                            raise ControlError("Private registration deadline exceeded.")
                        line, _, remainder = pending.partition(b"\n")
                        pending = bytearray(remainder)
                        message = _json(line)
                        if set(message) != {"type", "values"} or message["type"] != "secrets":
                            raise ControlError("Malformed private registration.")
                        registrations += 1
                        if registrations > MAX_REGISTRATIONS:
                            raise ControlError("Too many private registrations.")
                        registry.register(message["values"])
                        if not _remaining(deadline):
                            raise ControlError("Private registration deadline exceeded.")
                        # The registry is committed before acknowledgement becomes writable.
                        last_ack = writer.send(_ACK)
                if problem is not None:
                    break
            if problem is not None:
                break
            if not _remaining(deadline):
                timed_out = not exited
                problem = "Worker hard deadline exceeded" if timed_out else "Worker output drain was not completed"
                break
            if writer.failed:
                raise ControlError("Private stdin delivery failed.")
            if process.poll() is not None and not exited:
                exited = True
                cleanup_deadline = min(final_deadline, time.monotonic() + cleanup_timeout)
            if readers["control"].eof and (pending or not registrations):
                raise ControlError("Private registration handshake was not completed.")
            if (exited and all(reader.eof for reader in readers.values())
                    and writer.finished(initial_ticket) and writer.finished(last_ack)):
                break
            deadline = cleanup_deadline if exited else run_deadline
            _IDLE.wait(min(_PAUSE, _remaining(deadline)))
    except KeyboardInterrupt:
        problem = "Worker supervision was interrupted"
    except Exception:
        timed_out = not exited and not _remaining(run_deadline)
        problem = "Worker supervision or private registration failed"

    if cleanup_deadline is None:
        cleanup_deadline = min(final_deadline, time.monotonic() + cleanup_timeout)
    if problem is not None:
        for buffer in buffers.values():
            buffer.clear()
        if process is not None:
            try:
                running = process.poll() is None
            except Exception:
                running = True
            if running:
                kill_requested = True
                try:
                    process.kill()
                except KeyboardInterrupt:
                    try:
                        if _remaining(cleanup_deadline):
                            process.kill()
                    except BaseException:
                        pass
                except Exception:
                    pass
    if process is not None:
        try:
            if process.poll() is None:
                process.wait(timeout=_remaining(cleanup_deadline))
        except BaseException:
            problem = problem or "Owned child termination was not confirmed"
    if writer is not None:
        try:
            if not writer.stop(_remaining(cleanup_deadline)) or writer.failed:
                problem = problem or "Private pipe cleanup was not completed"
        except BaseException:
            problem = problem or "Private pipe cleanup failed"
    elif process is not None and process.stdin is not None:
        try:
            process.stdin.close()
        except BaseException:
            problem = problem or "Private stdin pipe cleanup failed"
    for stream in (getattr(process, "stdout", None), getattr(process, "stderr", None), control_stream):
        if stream is not None:
            try:
                stream.close()
            except BaseException:
                problem = problem or "Worker output pipe cleanup failed"
    pending.clear()
    status = getattr(process, "returncode", None)
    terminated = kill_requested and type(status) is int
    if problem is None:
        try:
            filtered_stdout = registry.redact(buffers["stdout"].decode("utf-8"))
            filtered_stderr = registry.redact(buffers["stderr"].decode("utf-8"))
            if (len(filtered_stdout.encode("utf-8")) + len(filtered_stderr.encode("utf-8")) > output_limit
                    or type(status) is not int):
                raise ValueError
        except Exception:
            problem = "Completed worker output could not be safely filtered"
    for buffer in buffers.values():
        buffer.clear()
    if problem is not None:
        exit_code = status if type(status) is int and status != 0 else (124 if timed_out else 70)
        note = " Child termination is unverified." if kill_requested and not terminated else ""
        return Result(exit_code, "", problem + ". Output suppressed; transaction outcome is unverified."
                      + note + "\n", timed_out, terminated)
    return Result(status, filtered_stdout, filtered_stderr, False, False)


def supervise(spec: dict, *, run_timeout=120, cleanup_timeout=5,
              output_limit=DEFAULT_OUTPUT_LIMIT) -> Result:
    """Defer Ctrl+C only while owning a child, then report interruption as failure.

    The handler records rather than raises during bounded kill/reap/drain. It is
    restored after all owned resources have been handled, never persisted.
    """
    interrupted = threading.Event()
    previous = None
    installed = threading.current_thread() is threading.main_thread()
    if installed:
        previous = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, lambda number, frame: interrupted.set())
    try:
        result = _supervise(spec, run_timeout=run_timeout, cleanup_timeout=cleanup_timeout,
                            output_limit=output_limit, interrupted=interrupted)
        if interrupted.is_set() and result.exit_code == 0:
            return Result(130, "", "Supervision interrupted; output suppressed and transaction outcome unverified.\n",
                          result.timed_out, result.terminated)
        return result
    finally:
        if installed:
            signal.signal(signal.SIGINT, previous)
