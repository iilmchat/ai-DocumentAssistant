# Документация проекта AI Document Assistant

## Содержание
1. **Архитектура (`/docs/architecture/`)**
   - [Обзор системы](architecture/system-overview.md)
   - [Схема базы данных](architecture/database-schema.md)
   - [RAG-пайплайн](architecture/rag-pipeline.md)
2. **Разработка (`/docs/development/`)**
   - [Быстрый старт и настройка окружения](development/getting-started.md)
   - [Руководство по Backend](development/backend-guide.md)
   - [Руководство по Frontend](development/frontend-guide.md)
   - [Оценка качества RAG](development/rag-eval.md)
3. **API (`/docs/openapi/`)**
   - [Спецификация эндпоинтов](openapi/endpoints.md)
4. **Эксплуатация (`/docs/operations/`)**
   - [Развертывание в Docker](operations/deployment.md)
   - [Устранение неполадок (Troubleshooting)](operations/troubleshooting.md)
   - [SLO и runbook наблюдаемости](operations/runbook.md)
   - [Нагрузочное тестирование](operations/load-test.md)
   - [Стейдж-прогон и учения](operations/stage-runbook.md)
   - [Масштабирование (T9)](operations/scaling.md)
   - [Живой smoke на Docker Desktop](operations/docker-desktop-smoke.md)
   - [Backup и Restore](operations/backup-restore.md)
5. **Безопасность (`/docs/security/`)**
   - [Управление ключами и доступом](security/security-overview.md)
   - [Threat model](security/threat-model.md)
   - [Hardening T8: cookie/CSRF/PII/RBAC](security/hardening.md)
6. **Руководство пользователя (`/docs/user_guide/`)**
   - [Инструкция по работе с системой](user_guide/how-to-use.md)
   - [Перевод документов](user_guide/translation.md)
