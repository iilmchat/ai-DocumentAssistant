# AI Document Assistant

Приложение для автоматического конспектирования документов (PDF, DOCX, TXT) и интерактивного RAG-чата по их содержимому.

## Быстрый запуск через Docker Compose

1. Создайте файл `backend/.env` на основе `backend/.env.example` и впишите свой ключ `OPENAI_API_KEY`:
   ```bash
   cp backend/.env.example backend/.env
   ```
2. Запустите весь стек одной командой из корня проекта:
   ```bash
   docker compose up --build -d
   ```
3. Откройте в браузере:
   - **Веб-интерфейс:** http://localhost
   - **Swagger API документация:** http://localhost:8000/docs
