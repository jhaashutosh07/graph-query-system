from app.guardrails import Guardrails, QueryCategory


def test_guardrails_accepts_domain_query_with_multiple_keywords():
    guardrails = Guardrails()
    result = guardrails.check_query("Which products are in the most orders?")
    assert result.is_valid is True
    assert result.category == QueryCategory.IN_SCOPE


def test_guardrails_rejects_poem_query():
    guardrails = Guardrails()
    result = guardrails.check_query("Write a poem about shipping")
    assert result.is_valid is False
    assert result.category == QueryCategory.OUT_OF_SCOPE


def test_guardrails_rejects_empty_or_whitespace():
    guardrails = Guardrails()
    result = guardrails.check_query("   ")
    assert result.is_valid is False

