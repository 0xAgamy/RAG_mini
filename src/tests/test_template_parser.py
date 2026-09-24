from __future__ import annotations

from stores.llm.templates.template_parser import TemplateParser


def test_template_parser_uses_default_english_templates():
    parser = TemplateParser()

    system_prompt = parser.get("rag", "system_prompt")
    document_prompt = parser.get(
        "rag",
        "document_prompt",
        {"doc_number": 1, "chunk_text": "A relevant document."},
    )

    assert parser.language == "en"
    assert "assistant" in system_prompt
    assert document_prompt == (
        "## Document No: 1 \n### Content: A relevant document. "
    )


def test_template_parser_supports_arabic_locale():
    parser = TemplateParser(language="ar")

    footer = parser.get(
        "rag",
        "footer_prompt",
        {"query": "ما هو RAG؟"},
    )

    assert parser.language == "ar"
    assert "ما هو RAG؟" in footer


def test_template_parser_falls_back_for_unknown_language():
    parser = TemplateParser(language="not-a-language")

    assert parser.language == "en"
    assert parser.get("rag", "system_prompt")


def test_template_parser_returns_none_for_missing_group_or_key_input():
    parser = TemplateParser()

    assert parser.get("", "system_prompt") is None
    assert parser.get("rag", "") is None
    assert parser.get("does_not_exist", "system_prompt") is None


def test_template_parser_can_switch_languages_explicitly():
    parser = TemplateParser()
    parser.set_language("ar")
    assert parser.language == "ar"

    parser.set_language(None)
    assert parser.language == "en"
