# S5: оценка качества RAG

## Офлайн-регрессия (в CI)

```bash
cd backend
python -m eval.rag_eval --offline
```

Скрипт читает `eval/questions.json` (зафиксированные вопросы, ожидаемые ключевые слова,
контекст и эталонный ответ), считает:

- **recall@k** — доля ожидаемых ключевых слов в найденном контексте;
- **faithfulness** — доля слов ответа, присутствующих в контексте (эвристика);
- **citation** — наличие ссылки `(стр. N)`;
- итоговый `score = 0.5*recall + 0.3*faithfulness + 0.2*citation`.

Отчёт пишется в `eval/report.json` (не коммитится). Порог по умолчанию — 0.7,
при падении CI красный. Текущий результат: **0.983**.

## Онлайн-оценка (ручная)

Для реальных запросов используйте `GET /api/v1/auth/usage` (токены и стоимость) и
метрики Grafana: `rag_queries_total`, `vector_search_duration_seconds`,
`rerank_duration_seconds`, `llm_calls_total`.

## Как добавить кейс

Добавьте объект в `eval/questions.json` с полями `id`, `question`, `expected_keywords`,
`context`, `answer`. После изменения промптов (`app/core/prompts.py`) прогон покажет регрессию.
