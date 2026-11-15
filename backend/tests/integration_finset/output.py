"""In-memory redaction for complete, bounded worker output. Never stream raw chunks."""

import json
import re
from threading import RLock
from urllib.parse import quote, quote_plus


SECRET_LIMIT = 65536
MAX_SECRETS = 128
_VARIANT_LIMIT = 1048576
_CONNECTION_URL = re.compile(
    r"(?i)\bpostgres(?:ql)?(?:(?:\+|%2b)[a-z0-9_.-]+)?"
    r"(?:://|%3a%2f%2f)[^\s]+"
)


class OutputError(ValueError):
    """A fail-closed output error whose message contains no supplied values."""


def _variants(value):
    variants = {value}
    for encoded in (quote(value, safe=""), quote(value), quote_plus(value, safe="")):
        variants.add(encoded)
    for encoded in (json.dumps(value, ensure_ascii=True), json.dumps(value, ensure_ascii=False)):
        variants.update((encoded, encoded[1:-1]))
    for encoded in (repr(value), ascii(value)):
        variants.update((encoded, encoded[1:-1]))
    encoded = repr(value.encode("utf-8"))
    variants.update((encoded, encoded[2:-1]))
    return variants


def _literal_pattern(value):
    # Percent escapes are case-insensitive without making raw credentials so.
    return re.sub(
        r"%([0-9a-fA-F]{2})",
        lambda match: "%" + "".join(
            "[" + char.lower() + char.upper() + "]" if char.isalpha() else char
            for char in match.group(1)
        ),
        re.escape(value),
    )


class SecretFilter:
    """A bounded, cumulative registry; failed registration changes nothing.

    Values must be a list or tuple of nonempty UTF-8 strings. An empty list is
    allowed for the collection/probe handshake. Only completed output should be
    passed to redact(): a truncated secret prefix cannot be safely released.
    """

    def __init__(self):
        self._values = ()
        self._pattern = None
        self._lock = RLock()

    def __repr__(self):
        return "<SecretFilter>"

    def register(self, values):
        __tracebackhide__ = True
        with self._lock:
            try:
                if type(values) not in (list, tuple) or len(values) > MAX_SECRETS:
                    raise ValueError
                if any(type(value) is not str or not value or len(value) > SECRET_LIMIT for value in values):
                    raise ValueError
                combined = tuple(dict.fromkeys(self._values + tuple(values)))
                if (len(combined) > MAX_SECRETS
                        or sum(len(value.encode("utf-8")) for value in combined) > SECRET_LIMIT):
                    raise ValueError
                if combined == self._values:
                    return
                variants = set()
                size = 0
                for value in combined:
                    for variant in _variants(value):
                        if variant not in variants:
                            size += len(variant.encode("utf-8"))
                            if size > _VARIANT_LIMIT:
                                raise ValueError
                            variants.add(variant)
                pattern = re.compile("|".join(
                    _literal_pattern(value) for value in sorted(variants, key=len, reverse=True)
                )) if variants else None
            except Exception:
                raise OutputError("Private secret registration is invalid or exceeds its limit.") from None
            self._values, self._pattern = combined, pattern

    def redact(self, text):
        __tracebackhide__ = True
        if type(text) is not str:
            raise OutputError("Only decoded, completed worker output can be filtered.")
        with self._lock:
            if self._pattern is not None:
                text = self._pattern.sub("[REDACTED]", text)
            return _CONNECTION_URL.sub("[REDACTED_CONNECTION_URL]", text)
