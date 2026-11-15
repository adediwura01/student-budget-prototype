"""DB-free fingerprints; frozen revision bytes are never imported or executed."""

from hashlib import sha256
from pathlib import Path

import pytest

from tests.integration_finset import schema


PINNED_SOURCE_SHA256 = "c231e71cdb1431e91216fa4a977cb248f5fd076a7fd4f9d84f964ff7b7f2fd99"
SOURCE_PATH = schema.BACKEND / "migrations" / "versions" / "0001_initial_finset_schema.py"
SYNTHETIC_SOURCE = (
    b"# synthetic source comment  \n"
    b"def synthetic():\n"
    b"    return 'synthetic literal' \t\n"
)


@pytest.mark.parametrize("source", [
    pytest.param(SYNTHETIC_SOURCE, id="lf"),
    pytest.param(SYNTHETIC_SOURCE.replace(b"\n", b"\r\n"), id="crlf"),
    pytest.param(SYNTHETIC_SOURCE.replace(b"\n", b"\r\n", 1), id="mixed-lf-crlf"),
])
def test_line_ending_variants_have_identical_canonical_bytes_and_fingerprints(source):
    canonical = schema.canonical_source(source)
    assert canonical == SYNTHETIC_SOURCE
    assert sha256(canonical).digest() == sha256(SYNTHETIC_SOURCE).digest()


def test_canonical_source_preserves_every_non_cr_byte():
    source = bytes(value for value in range(256) if value != 13)
    assert schema.canonical_source(source) == source
    assert schema.canonical_source(b"") == b""


def test_canonical_source_preserves_bom_trailing_whitespace_and_final_newlines():
    source = b"\xef\xbb\xbf# synthetic \t\r\nvalue = 'synthetic' \t\r\n\r\n"
    expected = b"\xef\xbb\xbf# synthetic \t\nvalue = 'synthetic' \t\n\n"
    canonical = schema.canonical_source(source)
    assert canonical == expected
    assert sha256(canonical).digest() != sha256(canonical.removeprefix(b"\xef\xbb\xbf")).digest()


@pytest.mark.parametrize("source", [
    pytest.param(b"\r", id="only-cr"),
    pytest.param(b"one\rtwo\n", id="embedded-cr"),
    pytest.param(b"one\r\ntwo\rthree\n", id="mixed-paired-and-lone-cr"),
    pytest.param(b"one\r\r\n", id="cr-before-crlf"),
    pytest.param(b"one\n\r", id="terminal-cr"),
    pytest.param(b"\r\n\r", id="lone-cr-after-crlf"),
])
def test_canonical_source_rejects_every_lone_carriage_return(source):
    with pytest.raises(schema.SafetyError, match="Frozen schema source is inconsistent"):
        schema.canonical_source(source)


@pytest.mark.parametrize("changed", [
    pytest.param(
        SYNTHETIC_SOURCE.replace(b"'synthetic literal'", b"'synthetic changed literal'"),
        id="literal-change",
    ),
    pytest.param(
        SYNTHETIC_SOURCE.replace(b"source comment", b"changed comment"),
        id="comment-change",
    ),
    pytest.param(SYNTHETIC_SOURCE.replace(b"    return", b"\treturn"), id="indent-change"),
    pytest.param(SYNTHETIC_SOURCE.replace(b" \t\n", b"\n"), id="trailing-whitespace-change"),
    pytest.param(SYNTHETIC_SOURCE.removesuffix(b"\n"), id="removed-final-newline"),
    pytest.param(SYNTHETIC_SOURCE + b"\n", id="added-final-newline"),
])
def test_non_line_ending_source_changes_remain_fingerprint_significant(changed):
    canonical = schema.canonical_source(changed)
    assert canonical == changed
    assert sha256(canonical).digest() != sha256(SYNTHETIC_SOURCE).digest()


@pytest.mark.parametrize("crlf_count", [0, -1, 1], ids=["lf", "crlf", "mixed-lf-crlf"])
def test_actual_frozen_source_retains_the_unchanged_pinned_fingerprint(crlf_count):
    canonical = schema.canonical_source(SOURCE_PATH.read_bytes())
    variant = canonical.replace(b"\n", b"\r\n", crlf_count)
    assert schema.SOURCE_SHA256 == PINNED_SOURCE_SHA256
    assert sha256(canonical).hexdigest() == PINNED_SOURCE_SHA256
    assert schema.canonical_source(variant) == canonical
    assert sha256(schema.canonical_source(variant)).hexdigest() == PINNED_SOURCE_SHA256


@pytest.mark.parametrize("crlf_count", [0, -1, 1], ids=["lf", "crlf", "mixed-lf-crlf"])
def test_manifest_checks_canonical_fingerprint_before_ast_without_executing_source(monkeypatch, crlf_count):
    canonical = schema.canonical_source(SOURCE_PATH.read_bytes())
    variant = canonical.replace(b"\n", b"\r\n", crlf_count)
    read_paths = []
    parse_calls = []

    def frozen_bytes(path):
        read_paths.append(path)
        return variant

    def stop_at_ast(source, *, filename):
        parse_calls.append((source, filename))
        raise SyntaxError("Synthetic stop before AST interpretation.")

    monkeypatch.setattr(Path, "read_bytes", frozen_bytes)
    monkeypatch.setattr(schema.ast, "parse", stop_at_ast)
    # Bypass only the metadata cache; the mocked AST boundary prevents interpretation.
    with pytest.raises(schema.SafetyError, match="Frozen schema manifest is unavailable or inconsistent"):
        schema.manifest.__wrapped__()
    assert read_paths == [SOURCE_PATH]
    assert parse_calls == [(canonical, "0001_initial_finset_schema.py")]
    assert schema.SOURCE_SHA256 == PINNED_SOURCE_SHA256


@pytest.mark.parametrize("source", [
    pytest.param(SYNTHETIC_SOURCE, id="unpinned-source"),
    pytest.param(b"def (\n", id="unpinned-invalid-syntax"),
    pytest.param(SYNTHETIC_SOURCE + b"\r", id="lone-cr"),
])
def test_manifest_rejects_unpinned_or_lone_cr_source_before_ast(monkeypatch, source):
    read_paths = []
    parse_calls = []

    def frozen_bytes(path):
        read_paths.append(path)
        return source

    def forbidden_ast(*args, **kwargs):
        parse_calls.append((args, kwargs))
        raise AssertionError("Synthetic AST boundary must not be reached.")

    monkeypatch.setattr(Path, "read_bytes", frozen_bytes)
    monkeypatch.setattr(schema.ast, "parse", forbidden_ast)
    with pytest.raises(schema.SafetyError, match="Frozen schema manifest is unavailable or inconsistent"):
        schema.manifest.__wrapped__()
    assert read_paths == [SOURCE_PATH]
    assert parse_calls == []
    assert schema.SOURCE_SHA256 == PINNED_SOURCE_SHA256
