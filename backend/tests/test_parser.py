from app.services.document_parser import (
    split_text_into_chunks,
    split_text_into_sentences,
)


def test_split_into_sentences_keeps_abbreviations():
    text = "Это первое предложение. А это второе! И третье?"
    sentences = split_text_into_sentences(text)
    assert len(sentences) == 3
    assert all(isinstance(s, str) and s for s in sentences)


def test_split_into_chunks_does_not_cut_sentences():
    text = " ".join([f"Это предложение номер {i} с каким-то содержимым." for i in range(100)])
    chunks = split_text_into_chunks(text, max_chunk_size=120, chunk_overlap=20)
    assert len(chunks) > 1
    assert all(isinstance(c, str) and c for c in chunks)
    # каждое предложение целиком входит хотя бы в один чанк
    for i in range(100):
        sentence = f"Это предложение номер {i} с каким-то содержимым."
        assert any(sentence in c for c in chunks)


def test_split_into_chunks_empty():
    assert split_text_into_chunks("") == []
    assert split_text_into_chunks("   ") == []
