# Руководство по Frontend (React + Vite + TypeScript)

## Структура директории `frontend/`
```text
frontend/
├── src/
│   ├── api/            # HTTP-клиент (client.ts) для взаимодействия с /api/v1
│   ├── components/     # UI-компоненты (Sidebar, SummaryViewer, ChatPanel)
│   ├── types/          # TypeScript-интерфейсы документов и сообщений
│   ├── App.tsx         # Основной макет и управление состоянием
│   ├── main.tsx        # Точка входа React
│   └── vite-env.d.ts   # Декларация типов окружения Vite (import.meta.env)
├── nginx.conf          # Конфигурация Nginx для SPA и проксирования API
├── Dockerfile
└── package.json
```

## Сборка и локальная разработка
```bash
cd frontend
npm install
npm run dev
```

> **Примечание:** При использовании `import.meta.env` в TypeScript убедитесь, что файл `src/vite-env.d.ts` содержит директиву `/// <reference types="vite/client" />`.
