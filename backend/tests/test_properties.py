"""T10: property-based тесты чанкера и RRF (hypothesis)."""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.api.chat import reciprocal_rank_fusion
from app.core.pii import redact_pii
from app.services.document_parser import split_text_into_chunks
from app.services.translation import protect_placeholders, restore_placeholders


@given(text=st.text(min_size=0, max_size=500))
@settings(max_examples=50)
def test_chunking_never_loses_content(text):
    chunks = split_text_into_chunks(text, max_chunk_size=50, chunk_overlap=10)
    if not text.strip():
        assert chunks == []
        return
    joined = " ".join(chunks)
    # каждое предложение исходника должно присутствовать хотя бы в одном чанке
    for sentence in text.split("."):
        sentence = sentence.strip()
        if len(sentence) > 3:
            assert sentence in joined


@given(parts=st.lists(st.tuples(st.uuids(), st.text()), min_size=1, max_size=10))
@settings(max_examples=50)
def test_rrf_returns_unique_items(parts):
    rows = [(uid, text, None, None, None) for uid, text in parts]
    result = reciprocal_rank_fusion(rows, rows)
    ids = [row[0] for row in result]
    assert len(ids) == len(set(ids))


@given(text=st.text(min_size=0, max_size=500))
@settings(max_examples=50)
def test_placeholder_roundtrip(text):
    protected, mapping = protect_placeholders(text)
    assert restore_placeholders(protected, mapping) == text


@given(text=st.text(min_size=0, max_size=500))
@settings(max_examples=50)
def test_redaction_never_raises(text):
    result = redact_pii(text)
    assert isinstance(result, str)
