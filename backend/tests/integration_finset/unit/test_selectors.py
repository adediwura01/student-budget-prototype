"""Pure selector regressions, without integration markers or live fixtures."""

import pytest
from _pytest.mark import expression as pytest_expression

from tests.integration_finset import policy


INVALID_SELECTOR = "Invalid test selector; supplied values are withheld."
UNAVAILABLE_SELECTOR = (
    "Required pytest selector validation is unavailable; execution is prohibited."
)


class OlderParseError(Exception):
    """Model the parser exception used by older pytest releases."""


@pytest.mark.parametrize("keyword", [
    pytest.param("", id="empty"),
    pytest.param(" \t ", id="whitespace"),
    pytest.param("test_synthetic_case", id="bare-keyword"),
    pytest.param("not hash", id="negation"),
    pytest.param("case_one or (case_two and not case_three)", id="boolean-grammar"),
    pytest.param("True or False or None", id="literal-looking-bare-keywords"),
    pytest.param(
        r"suite/test_synthetic.py::Case[param-1] or synthetic\case+two",
        id="pytest-bare-keyword-punctuation",
    ),
])
def test_keyword_selectors_preserve_pytest_bare_keyword_grammar(keyword):
    assert policy.validate_selectors(keyword, "integration") is None


@pytest.mark.parametrize("marker", [
    pytest.param("", id="empty"),
    pytest.param(" \t ", id="whitespace"),
    pytest.param("integration", id="integration-name"),
    pytest.param("finset_integration", id="dedicated-name"),
    pytest.param("finset_committed", id="committed-name"),
    pytest.param("finset_concurrency", id="concurrency-name"),
    pytest.param("not not integration", id="repeated-negation"),
    pytest.param("(integration)and(not(finset_concurrency))", id="parenthesis-boundaries"),
    pytest.param(
        "\t(integration or finset_integration) and not "
        "(finset_committed or finset_concurrency) ",
        id="all-approved-names-and-operators",
    ),
])
def test_marker_selectors_accept_only_approved_bare_language(marker):
    assert policy.validate_selectors("", marker) is None


@pytest.mark.parametrize("marker", [
    pytest.param("synthetic_unknown_marker", id="unknown-name"),
    pytest.param("integration or synthetic_unknown_marker", id="or-hidden-name"),
    pytest.param("integration and synthetic_unknown_marker", id="and-hidden-name"),
    pytest.param(
        "integration or (finset_concurrency and synthetic_unknown_marker)",
        id="nested-hidden-name",
    ),
    pytest.param("finset_integration_extra", id="approved-name-prefix"),
    pytest.param("Integration", id="case-sensitive-name"),
    pytest.param("integration+finset_integration", id="uncovered-plus"),
    pytest.param("integration.extra", id="uncovered-dot"),
    pytest.param("integration/extra", id="uncovered-slash"),
    pytest.param("integration[extra]", id="uncovered-brackets"),
    pytest.param("integration\u00e9", id="uncovered-non-ascii"),
    pytest.param("'integration'", id="quoted-name"),
    pytest.param("integration # synthetic comment", id="comment"),
    pytest.param("integration(enabled=True)", id="marker-call-kwargs"),
    pytest.param("integration()", id="empty-call"),
    pytest.param("integration and", id="missing-operand"),
    pytest.param("integration finset_integration", id="missing-operator"),
    pytest.param("()", id="empty-parentheses"),
    pytest.param("(integration", id="unclosed-parenthesis"),
    pytest.param("integration)", id="unmatched-parenthesis"),
    pytest.param("integration\nor finset_integration", id="not-pytest-whitespace"),
])
def test_marker_selectors_reject_unknown_tokens_and_invalid_grammar(marker):
    with pytest.raises(policy.SafetyError) as error:
        policy.validate_selectors("", marker)
    assert str(error.value) == INVALID_SELECTOR
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__


@pytest.mark.parametrize("keyword", [
    pytest.param("synthetic_case(label='synthetic')", id="string-call-kwarg"),
    pytest.param("synthetic_case(count=-1)", id="integer-call-kwarg"),
    pytest.param("safe_keyword or synthetic_case(enabled=True)", id="or-hidden-call"),
    pytest.param(
        "safe_keyword and synthetic_case(enabled=False, value=None)",
        id="and-hidden-call",
    ),
    pytest.param("synthetic_case()", id="empty-call"),
    pytest.param("(", id="unclosed-parenthesis"),
    pytest.param("synthetic_case and", id="missing-operand"),
    pytest.param("'synthetic_case'", id="quoted-keyword"),
])
def test_keyword_selectors_reject_calls_and_sanitize_parser_errors(keyword):
    with pytest.raises(policy.SafetyError) as error:
        policy.validate_selectors(keyword, "integration")
    assert str(error.value) == INVALID_SELECTOR
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__


@pytest.mark.parametrize("marker,accepted", [
    pytest.param(
        "integration and finset_integration and not finset_committed", True,
        id="approved-expression",
    ),
    pytest.param("integration or synthetic_unknown_marker", False, id="or-hidden-name"),
    pytest.param("integration and synthetic_unknown_marker", False, id="and-hidden-name"),
    pytest.param("integration+finset_integration", False, id="complete-token-coverage"),
])
def test_older_parser_needs_only_compile_without_idents_or_evaluation(monkeypatch, marker, accepted):
    compiled = []

    class OlderExpression:
        __slots__ = ()

        @classmethod
        def compile(cls, value):
            compiled.append(value)
            return cls()

    monkeypatch.setattr(pytest_expression, "Expression", OlderExpression)
    keyword = "test_synthetic_case"
    if accepted:
        assert policy.validate_selectors(keyword, marker) is None
    else:
        with pytest.raises(policy.SafetyError) as error:
            policy.validate_selectors(keyword, marker)
        assert str(error.value) == INVALID_SELECTOR
    assert compiled == [keyword, marker]


@pytest.mark.parametrize("selector", ["keyword", "marker"])
@pytest.mark.parametrize("error_type,message", [
    pytest.param(SyntaxError, INVALID_SELECTOR, id="syntax-error"),
    pytest.param(OlderParseError, INVALID_SELECTOR, id="older-parse-error"),
    pytest.param(ValueError, INVALID_SELECTOR, id="value-error"),
    pytest.param(TypeError, INVALID_SELECTOR, id="type-error"),
    pytest.param(RuntimeError, INVALID_SELECTOR, id="unexpected-parser-error"),
    pytest.param(AttributeError, UNAVAILABLE_SELECTOR, id="unavailable-attribute"),
    pytest.param(ImportError, UNAVAILABLE_SELECTOR, id="unavailable-import"),
])
def test_parser_exceptions_are_fail_closed_and_sanitized(monkeypatch, selector, error_type, message):
    private_text = "synthetic_private_selector_not_a_credential"
    failing_input = "safe_keyword" if selector == "keyword" else "integration"

    class FailingExpression:
        @staticmethod
        def compile(value):
            if value == failing_input:
                raise error_type(private_text)
            return object()

    monkeypatch.setattr(pytest_expression, "Expression", FailingExpression)
    with pytest.raises(policy.SafetyError) as error:
        policy.validate_selectors("safe_keyword", "integration")
    assert str(error.value) == message
    assert private_text not in repr(error.value)
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__


@pytest.mark.parametrize("missing", ["Expression", "compile"])
def test_missing_selector_api_is_unavailable_without_fallback(monkeypatch, missing):
    if missing == "Expression":
        monkeypatch.delattr(pytest_expression, "Expression")
    else:
        monkeypatch.setattr(pytest_expression, "Expression", object)
    with pytest.raises(policy.SafetyError) as error:
        policy.validate_selectors("", "integration")
    assert str(error.value) == UNAVAILABLE_SELECTOR
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__
