"""S2: Prometheus-метрики приложения, LLM, OCR и фоновых задач."""

from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP request latency", ["method", "path"]
)
LLM_CALLS = Counter("llm_calls_total", "LLM/embedding API calls", ["operation", "status"])
LLM_TOKENS = Counter("llm_tokens_total", "LLM tokens used", ["operation"])
LLM_LATENCY = Histogram("llm_request_duration_seconds", "LLM call latency", ["operation"])
OCR_PAGES = Counter("ocr_pages_total", "Pages processed by OCR", ["method"])
OCR_LATENCY = Histogram("ocr_duration_seconds", "OCR duration")
CELERY_TASKS = Counter("celery_tasks_total", "Celery tasks", ["task", "status"])
CELERY_LATENCY = Histogram("celery_task_duration_seconds", "Celery task duration", ["task"])
RAG_QUERIES = Counter("rag_queries_total", "RAG queries")
SEARCH_LATENCY = Histogram("vector_search_duration_seconds", "Vector search duration")
DOCS_BY_STATUS = Gauge("documents_by_status", "Documents by status", ["status"])


def set_doc_status_gauge(counts: dict[str, int]) -> None:
    for status, count in counts.items():
        DOCS_BY_STATUS.labels(status=status).set(count)
