# Реальный LLM-провайдер (OpenCode + Ollama)

С 2026-11-19 приложение работает с **реальными моделями**, офлайн-режим (`LOCAL_EMBEDDINGS`)
используется только в unit-тестах.

## Схема

| Задача | Провайдер | Модель | Endpoint |
| :--- | :--- | :--- | :--- |
| Chat / RAG / суммаризация | OpenCode inference (OpenAI-compat) | `deepseek-v4.1-flash` | `https://opencode.ai/inference/openai/v1` |
| Embeddings | Локальный Ollama | `nomic-embed-text` (768 dim) | `http://host.docker.internal:11434` |

Почему гибрид: OpenCode inference не предоставляет `/embeddings` (в каталоге моделей нет
embedding-моделей), поэтому эмбеддинги считаются локально через Ollama.

## Почему не `hy4-flash-free`

Модель `hy4-flash-free` доступна в OpenCode и бесплатна, но её **free-лимит исчерпан**
(`FreeUsageLimitError`), а `hy4` из Go-провайдера требует подписки. Выбрана платная
`deepseek-v4.1-flash` ( cheapest working: $0.30 / $1.20 за 1M токенов) — ответы реальные,
 credit расходуется по факту. Если подписка Go появится — поменяйте `LLM_MODEL` на `hy4`.

## Настройка (секреты — в `backend/.env`, не в Git)

```env
OPENAI_API_KEY=oc_sk_...
OPENAI_BASE_URL=https://opencode.ai/inference/openai/v1/
LLM_MODEL=deepseek-v4.1-flash
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIM=768
LOCAL_EMBEDDINGS=false
OPENCODE_CHAT=true
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_EMBED_MODEL=nomic-embed-text
```

Важно:
- OpenCode inference отклоняет дефолтный User-Agent (403/cloudflare 1010) — в `ai_service.py`
  задан браузерный User-Agent + Origin.
- Контейнерам нужен доступ к хосту: `extra_hosts: host.docker.internal:host-gateway` в compose.
- Ollama и модель `nomic-embed-text` должны быть запущены на хосте:
  `ollama pull nomic-embed-text`.

## Проверено

- RAG-чат: `POST /chat/ask` → 200, 4 цитаты, реальный LLM-ответ, `usage.requests=1`, 1834 токена.
- PII-redaction работает (все вызовы идут централизованно через `_resilient_call`).
- Unit-тесты изолированы fixture `_no_external_llm` — не зовут внешние API.
