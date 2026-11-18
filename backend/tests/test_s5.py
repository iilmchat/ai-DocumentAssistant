import pytest

from app.core.prompts import prompt_meta, render
from eval.rag_eval import citation_presence, evaluate, faithfulness, recall_at_k


def test_prompt_registry_render():
    text = render("rag_user", context="контекст", question="вопрос")
    assert "контекст" in text
    assert "вопрос" in text
    assert render("rag_system")
    assert int(prompt_meta()["count"]) >= 10
    with pytest.raises(KeyError):
        render("missing")


def test_rag_metrics():
    assert recall_at_k("q", "оплата за 5 банковских дней", ["оплат", "дней"]) == 1.0
    assert recall_at_k("q", "ничего", ["оплат"]) == 0.0
    assert faithfulness("Оплата за 5 банковских дней", "Оплата за 5 банковских дней") == 1.0
    assert citation_presence("Ответ (стр. 3)") == 1.0
    assert citation_presence("Ответ без ссылки") == 0.0


def test_offline_eval_dataset():
    import json
    from pathlib import Path

    dataset = json.loads(
        (Path(__file__).parents[1] / "eval" / "questions.json").read_text(encoding="utf-8")
    )
    report = evaluate(dataset)
    assert report["aggregate"]["cases"] == len(dataset)
    assert report["aggregate"]["mean_score"] > 0.7
