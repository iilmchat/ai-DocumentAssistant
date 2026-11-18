"""S5: offline-оценка качества RAG (recall@k, faithfulness, citation presence).

Запуск: python -m eval.rag_eval --offline
Режим --offline использует зафиксированные контексты из questions.json и не зовёт LLM —
годится для регрессионного прогона в CI. Порог задаётся --min-score (по умолчанию 0.7).
"""

import argparse
import json
import re
from pathlib import Path

STOPWORDS = {
    "и",
    "в",
    "во",
    "не",
    "что",
    "это",
    "по",
    "на",
    "с",
    "со",
    "как",
    "каковы",
    "who",
    "the",
    "is",
    "of",
    "to",
    "in",
    "for",
    "a",
    "when",
    "what",
}

DATASET = Path(__file__).with_name("questions.json")
REPORT = Path(__file__).with_name("report.json")


def recall_at_k(question: str, context: str, keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    haystack = context.lower()
    hits = sum(1 for keyword in keywords if keyword.lower() in haystack)
    return hits / len(keywords)


def faithfulness(answer: str, context: str) -> float:
    tokens = [
        token.lower().strip('.,!?():;«»"')
        for token in re.split(r"\s+", answer)
        if len(token) > 3 and token.lower() not in STOPWORDS
    ]
    if not tokens:
        return 0.0
    haystack = context.lower()
    return sum(1 for token in tokens if token in haystack) / len(tokens)


def citation_presence(answer: str) -> float:
    return 1.0 if re.search(r"стр\.\s*\d+", answer, re.IGNORECASE) else 0.0


def evaluate(dataset: list[dict]) -> dict:
    rows = []
    for item in dataset:
        row = {
            "id": item["id"],
            "recall": round(
                recall_at_k(item["question"], item["context"], item["expected_keywords"]), 3
            ),
            "faithfulness": round(faithfulness(item["answer"], item["context"]), 3),
            "citation": citation_presence(item["answer"]),
        }
        row["score"] = round(
            row["recall"] * 0.5 + row["faithfulness"] * 0.3 + row["citation"] * 0.2, 3
        )
        rows.append(row)
    aggregate = {
        "cases": len(rows),
        "mean_recall": round(sum(r["recall"] for r in rows) / max(len(rows), 1), 3),
        "mean_faithfulness": round(sum(r["faithfulness"] for r in rows) / max(len(rows), 1), 3),
        "citation_rate": round(sum(r["citation"] for r in rows) / max(len(rows), 1), 3),
        "mean_score": round(sum(r["score"] for r in rows) / max(len(rows), 1), 3),
    }
    return {"aggregate": aggregate, "cases": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--offline", action="store_true", help="использовать questions.json без LLM"
    )
    parser.add_argument("--min-score", type=float, default=0.7)
    args = parser.parse_args()
    if not args.offline:
        parser.error(
            "сейчас поддерживается только --offline (детерминированный регрессионный прогон)"
        )

    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    report = evaluate(dataset)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["aggregate"], ensure_ascii=False, indent=2))
    if report["aggregate"]["mean_score"] < args.min_score:
        raise SystemExit(
            f"RAG quality regression: {report['aggregate']['mean_score']} < {args.min_score}"
        )


if __name__ == "__main__":
    main()
