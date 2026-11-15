"""Synthetic fakes and owned, DB-free worker probes only.

The parent test launcher preloads its deny-all unit guard. Real subprocess
cases always invoke the controlled worker in probe mode, where the worker must
also install that guard. No alternate interpreter scripts or sockets are used.
"""

from collections import deque
import json
import math
import os
import subprocess
import sys
import time
from unittest import TestCase, mock

from tests.integration_finset import supervisor
from tests.integration_finset.output import SecretFilter
from tests.integration_finset.probes import CANARY


SPEC = {"mode": "probe", "probe": "emit"}


def _frame(values):
    return (json.dumps({"type": "secrets", "values": values}, ensure_ascii=True,
                       separators=(",", ":")) + "\n").encode("ascii")


class _Stream:
    def __init__(self, chunks=()):
        self.chunks = deque(chunks)
        self.closed = False

    def close(self):
        self.closed = True


class _Reader:
    def __init__(self, stream):
        self.stream = stream
        self.eof = False

    def read(self, limit=65536):
        if self.eof:
            return b""
        if not self.stream.chunks:
            return None
        chunk = self.stream.chunks.popleft()
        if isinstance(chunk, Exception):
            raise chunk
        if chunk is not None and len(chunk) > limit:
            self.stream.chunks.appendleft(chunk[limit:])
            chunk = chunk[:limit]
        if chunk == b"":
            self.eof = True
        return chunk


class _Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def wait(self, timeout):
        if not math.isfinite(timeout) or timeout < 0:
            raise AssertionError("A wait must be finite and nonnegative.")
        self.now += timeout


class _Process:
    def __init__(self, stdout, stderr, status, clock, *, resists_kill=False):
        self.stdin = _Stream()
        self.stdout, self.stderr = stdout, stderr
        self.returncode = status
        self.clock = clock
        self.resists_kill = resists_kill
        self.kills = 0
        self.waits = []

    def poll(self):
        return self.returncode

    def kill(self):
        self.kills += 1
        if not self.resists_kill:
            self.returncode = -9

    def wait(self, *, timeout):
        self.waits.append(timeout)
        if self.returncode is None:
            self.clock.wait(timeout)
            raise subprocess.TimeoutExpired("synthetic-worker", timeout)
        return self.returncode


class _Writer:
    def __init__(self, stream, registry, *, fail_ack=False, complete_ack=True, stop_ok=True):
        self.stream = stream
        self.registry = registry
        self.fd = 99
        self.failed = False
        self.fail_ack = fail_ack
        self.complete_ack = complete_ack
        self.stop_ok = stop_ok
        self.messages = []
        self.ack_registered = []
        self.stops = []

    def send(self, payload):
        self.messages.append(payload)
        if payload == b'{"type":"ack"}\n':
            self.ack_registered.append(self.registry.redact(CANARY) == "[REDACTED]")
            self.failed = self.fail_ack
        return len(self.messages)

    def finished(self, ticket):
        return ticket <= len(self.messages) and (ticket <= 1 or self.complete_ack)

    def stop(self, timeout):
        self.stops.append(timeout)
        self.stream.close()
        return self.stop_ok


class TestSupervisorFakes(TestCase):
    def _supervise(self, *, stdout=(b"",), stderr=(b"",), control=None, status=0,
                   run_timeout=0.03, cleanup_timeout=0.05, output_limit=4096,
                   resists_kill=False, **writer_options):
        clock = _Clock()
        process = _Process(_Stream(stdout), _Stream(stderr), status, clock, resists_kill=resists_kill)
        private = _Stream((_frame([]), b"") if control is None else control)
        registry = SecretFilter()
        writer = _Writer(process.stdin, registry, **writer_options)
        with mock.patch.object(supervisor, "_spawn", return_value=(process, private)), \
                mock.patch.object(supervisor, "_PipeReader", _Reader), \
                mock.patch.object(supervisor, "_Writer", return_value=writer), \
                mock.patch.object(supervisor, "SecretFilter", return_value=registry), \
                mock.patch.object(supervisor.time, "monotonic", clock.monotonic), \
                mock.patch.object(supervisor, "_IDLE", clock):
            result = supervisor.supervise(SPEC, run_timeout=run_timeout,
                                          cleanup_timeout=cleanup_timeout, output_limit=output_limit)
        self.assertTrue(process.stdout.closed and process.stderr.closed and private.closed)
        self.assertTrue(writer.stops)
        self.assertTrue(all(math.isfinite(value) and value >= 0 for value in writer.stops + process.waits))
        return result, process, writer, clock

    def test_split_fd_output_waits_for_private_registration_and_preserves_status(self):
        value = CANARY.encode("utf-8")
        split = len(value) // 2
        frame = _frame([CANARY])
        result, process, writer, _ = self._supervise(
            stdout=(b"stdout fd1: " + value[:split], None, value[split:] + b"\n", b""),
            stderr=(b"stderr fd2: " + value, b"\n", b""),
            control=(frame[:12], None, frame[12:], b""), status=23,
        )
        self.assertEqual(result.exit_code, 23)
        self.assertEqual(result.stdout, "stdout fd1: [REDACTED]\n")
        self.assertEqual(result.stderr, "stderr fd2: [REDACTED]\n")
        self.assertEqual(writer.ack_registered, [True])
        self.assertEqual(json.loads(writer.messages[0]), SPEC)
        self.assertEqual(writer.messages[1], b'{"type":"ack"}\n')
        self.assertNotIn(CANARY.encode("utf-8"), b"".join(writer.messages))
        self.assertFalse(result.timed_out or result.terminated)
        self.assertEqual(process.kills, 0)

    def test_missing_registration_cannot_report_success(self):
        result, process, _, _ = self._supervise(stdout=(CANARY.encode("utf-8"), b""), control=(b"",))
        self.assertEqual(result.exit_code, 70)
        self.assertEqual(result.stdout, "")
        self.assertIn("unverified", result.stderr)
        self.assertNotIn(CANARY, result.stderr)
        self.assertEqual(process.kills, 0)

    def test_malformed_partial_and_invalid_private_messages_are_suppressed(self):
        malformed = [b"not-json\n", b"\xff\n", b"\n", _frame([CANARY])[:-1],
                     b'{"type":"secrets","type":"secrets","values":[]}\n',
                     b'{"type":"unexpected","values":[]}\n',
                     b'{"type":"secrets","values":[],"extra":true}\n',
                     b'{"type":"secrets","values":[NaN]}\n', _frame(CANARY)]
        for index, frame in enumerate(malformed):
            with self.subTest(case=index):
                result, process, _, _ = self._supervise(
                    stdout=(CANARY.encode("utf-8"), b""),
                    stderr=(CANARY.encode("utf-8"), b""), control=(frame, b""), status=None,
                )
                self.assertNotEqual(result.exit_code, 0)
                self.assertEqual(result.stdout, "")
                self.assertNotIn(CANARY, result.stderr)
                self.assertIn("unverified", result.stderr)
                self.assertEqual(process.kills, 1)
                self.assertTrue(result.terminated)

    def test_control_byte_and_registration_count_limits(self):
        for frame in (b"x" * (supervisor.CONTROL_LIMIT + 1),
                      _frame([]) * (supervisor.MAX_REGISTRATIONS + 1)):
            result, process, _, _ = self._supervise(control=(frame, None), status=None)
            self.assertNotEqual(result.exit_code, 0)
            self.assertEqual(result.stdout, "")
            self.assertEqual(process.kills, 1)
            self.assertFalse(result.timed_out)

    def test_ack_failure_and_unfinished_ack_never_release_output(self):
        for options in ({"fail_ack": True}, {"complete_ack": False}, {"stop_ok": False}):
            with self.subTest(case=next(iter(options))):
                result, _, _, clock = self._supervise(
                    stdout=(CANARY.encode("utf-8"), b""), control=(_frame([CANARY]), b""), **options,
                )
                self.assertNotEqual(result.exit_code, 0)
                self.assertEqual(result.stdout, "")
                self.assertNotIn(CANARY, result.stderr)
                self.assertLessEqual(clock.now, 0.08 + 0.000001)

    def test_hard_deadline_kills_only_owned_child_and_bounds_unreaped_cleanup(self):
        for resists in (False, True):
            with self.subTest(resists=resists):
                result, process, _, clock = self._supervise(
                    stdout=(None,), stderr=(None,), control=(_frame([]), None),
                    status=None, resists_kill=resists,
                )
                self.assertTrue(result.timed_out)
                self.assertEqual(process.kills, 1)
                self.assertEqual(result.terminated, not resists)
                self.assertEqual(result.exit_code, 124 if resists else -9)
                self.assertEqual(result.stdout, "")
                self.assertIn("unverified", result.stderr)
                self.assertLessEqual(clock.now, 0.08 + 0.000001)
                if resists:
                    self.assertTrue(process.waits)
                    self.assertLessEqual(sum(process.waits), 0.05 + 0.000001)

    def test_keyboard_interrupt_during_kill_does_not_escape_cleanup(self):
        original = _Process.kill
        def interrupted_kill(process):
            if process.kills == 0:
                process.kills += 1
                raise KeyboardInterrupt
            original(process)
        with mock.patch.object(_Process, "kill", interrupted_kill):
            result, process, writer, _ = self._supervise(
                stdout=(None,), stderr=(None,), control=(_frame([]), None), status=None)
        self.assertTrue(result.timed_out and result.terminated)
        self.assertEqual(process.kills, 2)
        self.assertTrue(writer.stops)

    def test_sigint_handler_is_restored_and_interrupted_success_is_not_reported(self):
        previous = supervisor.signal.getsignal(supervisor.signal.SIGINT)
        def finishing(*args, **kwargs):
            supervisor.signal.getsignal(supervisor.signal.SIGINT)(supervisor.signal.SIGINT, None)
            return supervisor.Result(0, "unreleased synthetic output", "", False, False)
        with mock.patch.object(supervisor, "_supervise", finishing):
            result = supervisor.supervise(SPEC)
        self.assertIs(supervisor.signal.getsignal(supervisor.signal.SIGINT), previous)
        self.assertEqual(result.exit_code, 130)
        self.assertEqual(result.stdout, "")

    def test_output_cap_read_errors_invalid_encoding_and_filtered_expansion(self):
        cases = [dict(stdout=(CANARY.encode("utf-8"),), status=None, output_limit=8),
                 dict(stdout=(OSError(CANARY),), status=None),
                 dict(stdout=(b"\xff", b"")),
                 dict(stdout=(b"aaaa", b""), control=(_frame(["a"]), b""), output_limit=4)]
        for index, options in enumerate(cases):
            with self.subTest(case=index):
                result, _, _, _ = self._supervise(**options)
                self.assertNotEqual(result.exit_code, 0)
                self.assertEqual(result.stdout, "")
                self.assertNotIn(CANARY, result.stderr)
                self.assertIn("unverified", result.stderr)

    def test_invalid_requests_do_not_spawn_or_echo_supplied_values(self):
        invalid = [dict(SPEC, password=CANARY), {"mode": "probe", "probe": CANARY},
                   {"mode": "live", "path": CANARY}, {"mode": "collect", "k": "\n" + CANARY},
                   {"mode": "collect", "q": CANARY}, {"mode": "collect", "v": True}]
        with mock.patch.object(supervisor, "_spawn") as spawn:
            for spec in invalid:
                result = supervisor.supervise(spec)
                self.assertEqual(result.exit_code, 4)
                self.assertNotIn(CANARY, result.stderr)
            for options in ({"run_timeout": float("nan")}, {"run_timeout": 0},
                            {"cleanup_timeout": float("inf")}, {"output_limit": True}):
                self.assertEqual(supervisor.supervise(SPEC, **options).exit_code, 4)
        spawn.assert_not_called()

    def test_spawn_uses_fixed_interpreter_cwd_pipes_and_numeric_private_handle(self):
        with mock.patch.dict(os.environ, {"PGPASSWORD": CANARY, "PYTHONPATH": CANARY,
                                          "FINSET_INTEGRATION_RUNTIME_DATABASE_URL": CANARY}), \
                mock.patch.object(supervisor.subprocess, "Popen", side_effect=OSError(CANARY)) as popen:
            result = supervisor.supervise(SPEC)
        self.assertEqual(result.exit_code, 70)
        self.assertNotIn(CANARY, result.stderr)
        popen.assert_called_once()
        args, kwargs = popen.call_args
        argv = args[0]
        self.assertEqual(argv[:-1], [sys.executable, "-u", "-B", "-m",
                                    "tests.integration_finset.worker", "--control"])
        self.assertTrue(argv[-1].isdigit())
        self.assertEqual(kwargs["cwd"], str(supervisor.cwdpolicy.BACKEND))
        self.assertTrue(kwargs["close_fds"])
        self.assertFalse(kwargs["shell"])
        self.assertEqual(kwargs["bufsize"], 0)
        for name in ("stdin", "stdout", "stderr"):
            self.assertEqual(kwargs[name], subprocess.PIPE)
        self.assertNotIn(CANARY, kwargs["env"].values())
        for name in ("PGPASSWORD", "PYTHONPATH", "FINSET_INTEGRATION_RUNTIME_DATABASE_URL"):
            self.assertNotIn(name, kwargs["env"])
        if os.name == "nt":
            self.assertEqual(kwargs["startupinfo"].lpAttributeList["handle_list"], [int(argv[-1])])
        else:
            self.assertEqual(kwargs["pass_fds"], (int(argv[-1]),))


class TestControlClientFakes(TestCase):
    def _client(self, chunks):
        stream = _Stream()
        writer = _Writer(stream, SecretFilter())
        reader = _Reader(_Stream(chunks))
        with mock.patch.object(supervisor.os, "fstat", return_value=mock.Mock(st_mode=supervisor.stat.S_IFIFO)), \
                mock.patch.object(supervisor.os, "set_inheritable"), \
                mock.patch.object(supervisor.os, "fdopen", return_value=stream), \
                mock.patch.object(supervisor, "_Writer", return_value=writer), \
                mock.patch.object(supervisor, "_PipeReader", return_value=reader):
            client = supervisor.ControlClient(99, stdin_fd=98)
        return client, writer

    def test_initial_spec_and_split_ack_use_stdin_only(self):
        clock = _Clock()
        initial = json.dumps(SPEC).encode("ascii") + b"\n"
        client, writer = self._client((initial, None, b'{"type":', None, b'"ack"}\n'))
        with mock.patch.object(supervisor.time, "monotonic", clock.monotonic), \
                mock.patch.object(supervisor, "_IDLE", clock):
            self.assertEqual(client.receive_spec(timeout=0.03), SPEC)
            client.secret_registration([CANARY], timeout=0.03)
            client.close(timeout=0)
        self.assertEqual(writer.messages, [_frame([CANARY])])
        self.assertLessEqual(clock.now, 0.03)

    def test_bad_missing_and_oversize_ack_fail_closed_with_bounded_wait(self):
        initial = json.dumps(SPEC).encode("ascii") + b"\n"
        for ack in (b'{"type":"wrong"}\n', b'{"type":"ack","extra":true}\n',
                    b'{"type":"ack","type":"ack"}\n', b"x" * 65, None):
            clock = _Clock()
            client, writer = self._client((initial, ack))
            with mock.patch.object(supervisor.time, "monotonic", clock.monotonic), \
                    mock.patch.object(supervisor, "_IDLE", clock):
                client.receive_spec(timeout=0.03)
                with self.assertRaises(supervisor.ControlError) as raised:
                    client.secret_registration([CANARY], timeout=0.03)
            self.assertNotIn(CANARY, str(raised.exception))
            self.assertTrue(client._closed)
            self.assertEqual(writer.stops, [0])
            self.assertLessEqual(clock.now, 0.03 + 0.000001)

    def test_standard_descriptors_and_nonnumeric_handles_are_rejected(self):
        with mock.patch.object(supervisor, "ControlClient") as client:
            for number in (0, 1, 2, -1, True, "3"):
                with self.assertRaises(supervisor.ControlError):
                    supervisor.open_control(number)
        client.assert_not_called()


class TestOwnedProbeSubprocesses(TestCase):
    def test_emit_captures_os_fd_channels_and_filters_synthetic_canary(self):
        result = supervisor.supervise(SPEC, run_timeout=10, cleanup_timeout=1)
        self.assertEqual(result.exit_code, 0)
        self.assertFalse(result.timed_out or result.terminated)
        self.assertIn("stdout fd1: [REDACTED]", result.stdout)
        self.assertIn("stderr fd2: [REDACTED]", result.stderr)
        self.assertNotIn("stderr fd2", result.stdout)
        self.assertNotIn("stdout fd1", result.stderr)
        self.assertNotIn(CANARY, result.stdout + result.stderr)
        self.assertIn("[REDACTED_CONNECTION_URL]", result.stderr)

    def test_hang_is_deadline_owned_and_termination_is_confirmed(self):
        start = time.monotonic()
        result = supervisor.supervise({"mode": "probe", "probe": "hang"},
                                      run_timeout=0.2, cleanup_timeout=1)
        elapsed = time.monotonic() - start
        self.assertTrue(result.timed_out)
        self.assertTrue(result.terminated)
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("unverified", result.stderr)
        self.assertLess(elapsed, 4)

    def test_bad_control_oversize_and_output_limit_are_not_successful_runs(self):
        cases = [({"mode": "probe", "probe": name}, 4096) for name in ("bad_control", "oversize")]
        cases.append((SPEC, 16))
        for spec, limit in cases:
            with self.subTest(probe=spec["probe"], limit=limit):
                result = supervisor.supervise(spec, run_timeout=10, cleanup_timeout=1, output_limit=limit)
                self.assertNotEqual(result.exit_code, 0)
                self.assertFalse(result.timed_out)
                self.assertEqual(result.stdout, "")
                self.assertNotIn(CANARY, result.stderr)
                self.assertNotIn("unverified synthetic", result.stderr)
                self.assertIn("unverified", result.stderr)
