"""Pure synthetic redaction tests; no credentials, configuration or database."""

import json
import re
from unittest import TestCase
from urllib.parse import quote, quote_plus

from tests.integration_finset.output import MAX_SECRETS, SECRET_LIMIT, OutputError, SecretFilter


CANARY = 'synthetic-output-canary:/p a"ss\\\u00e9\t\n'


class TestSecretFilter(TestCase):
    def test_raw_url_json_and_bytes_repr_variants(self):
        registry = SecretFilter()
        registry.register([CANARY])
        variants = [CANARY, quote(CANARY, safe=""), quote(CANARY), quote_plus(CANARY),
                    json.dumps(CANARY), json.dumps(CANARY)[1:-1],
                    json.dumps(CANARY, ensure_ascii=False),
                    json.dumps(CANARY, ensure_ascii=False)[1:-1],
                    repr(CANARY), ascii(CANARY), repr(CANARY.encode("utf-8")),
                    repr(CANARY.encode("utf-8"))[2:-1]]
        encoded = quote(CANARY, safe="")
        variants.append(re.sub(r"%[0-9A-F]{2}", lambda match: match.group().lower(), encoded))
        variants.append(re.sub(r"%[0-9A-F]{2}",
                               lambda match: "%" + match.group()[1].lower() + match.group()[2], encoded))
        for value in variants:
            with self.subTest(variant=variants.index(value)):
                self.assertEqual(registry.redact("before " + value + " after"),
                                 "before [REDACTED] after")

    def test_connection_urls_are_redacted_even_without_registration(self):
        registry = SecretFilter()
        url = "postgresql+psycopg://synthetic:synthetic@127.0.0.1/synthetic"
        for value in (url, quote(url, safe=""), "postgres://synthetic:synthetic@localhost/synthetic"):
            with self.subTest(encoded=value != url):
                self.assertEqual(registry.redact("connection " + value + "\nbenign"),
                                 "connection [REDACTED_CONNECTION_URL]\nbenign")

    def test_registration_is_cumulative_and_longest_match_wins(self):
        registry = SecretFilter()
        registry.register(["synthetic-token"])
        registry.register(("synthetic-token-expanded", "synthetic-token"))
        registry.register([])
        self.assertEqual(registry.redact("synthetic-token-expanded synthetic-token"),
                         "[REDACTED] [REDACTED]")

    def test_invalid_or_oversize_registration_is_atomic_and_withheld(self):
        registry = SecretFilter()
        registry.register([CANARY])
        invalid = [CANARY, ["synthetic-new", None], [b"synthetic-bytes"], [""], ["\ud800"],
                   ["x" * (SECRET_LIMIT + 1)],
                   ["synthetic-" + str(index) for index in range(MAX_SECRETS + 1)]]
        for index, values in enumerate(invalid):
            with self.subTest(case=index):
                with self.assertRaises(OutputError) as raised:
                    registry.register(values)
                self.assertNotIn(CANARY, str(raised.exception))
                self.assertEqual(registry.redact(CANARY), "[REDACTED]")
                self.assertEqual(registry.redact("synthetic-new"), "synthetic-new")

    def test_benign_output_and_registry_repr(self):
        registry = SecretFilter()
        registry.register([])
        self.assertEqual(registry.redact("stdout\nstderr\t42"), "stdout\nstderr\t42")
        registry.register([CANARY])
        self.assertNotIn(CANARY, repr(registry))
        with self.assertRaises(OutputError):
            registry.redact(CANARY.encode("utf-8"))
