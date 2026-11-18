import { useEffect, useState } from 'react'

export type Lang = 'ru' | 'en'

const dict = {
  ru: {
    appName: 'AI Конспект',
    appSubtitle: 'Анализ документов и RAG-чат',
    upload: 'Загрузить документ',
    uploading: 'Загрузка файла...',
    formats: 'PDF, DOCX, TXT, JPG, PNG, TIFF',
    yourDocs: 'Ваши документы',
    noDocs: 'Документов пока нет',
    noDocsHint: 'Загрузите первый файл для конспекта',
    selectDoc: 'Выберите или загрузите документ',
    selectDocHint:
      'Загрузите PDF, DOCX, TXT или изображение — ИИ составит конспект и ответит на вопросы.',
    summaryTab: 'Конспект',
    chatTab: 'Чат по документу',
    pagesTab: 'Страницы',
    askPlaceholder: 'Спросите что-нибудь о содержании документа...',
    waitProcessing: 'Дождитесь завершения обработки документа...',
    send: 'Спросить',
    stop: 'Стоп',
    askTitle: 'Задайте вопрос по документу',
    askHint: 'ИИ найдёт релевантные фрагменты и сформулирует ответ с цитатами.',
    sources: 'Источники из документа',
    good: 'Готов',
    analyzing: 'Анализ...',
    queued: 'В очереди',
    failed: 'Ошибка',
    loginTitle: 'С возвращением',
    registerTitle: 'Создать аккаунт',
    email: 'Email',
    password: 'Пароль',
    login: 'Войти',
    register: 'Зарегистрироваться',
    toRegister: 'Нет аккаунта? Зарегистрироваться',
    toLogin: 'Уже есть аккаунт? Войти',
    summaryTitle: 'Умный конспект документа',
    copy: 'Копировать',
    copied: 'Скопировано',
    refresh: 'Обновить',
    history: 'История версий',
    processing: 'ИИ изучает ваш документ...',
    errorBoundary: 'Что-то пошло не так',
    reload: 'Перезагрузить',
  },
  en: {
    appName: 'AI Summary',
    appSubtitle: 'Document analysis & RAG chat',
    upload: 'Upload document',
    uploading: 'Uploading...',
    formats: 'PDF, DOCX, TXT, JPG, PNG, TIFF',
    yourDocs: 'Your documents',
    noDocs: 'No documents yet',
    noDocsHint: 'Upload a file to generate a summary',
    selectDoc: 'Select or upload a document',
    selectDocHint: 'Upload a PDF, DOCX, TXT or image — AI will summarize it and answer questions.',
    summaryTab: 'Summary',
    chatTab: 'Document chat',
    pagesTab: 'Pages',
    askPlaceholder: 'Ask something about the document...',
    waitProcessing: 'Wait until processing finishes...',
    send: 'Ask',
    stop: 'Stop',
    askTitle: 'Ask a question about the document',
    askHint: 'AI will find relevant fragments and answer with citations.',
    sources: 'Sources from the document',
    good: 'Ready',
    analyzing: 'Analyzing...',
    queued: 'Queued',
    failed: 'Failed',
    loginTitle: 'Welcome back',
    registerTitle: 'Create account',
    email: 'Email',
    password: 'Password',
    login: 'Sign in',
    register: 'Sign up',
    toRegister: 'No account? Sign up',
    toLogin: 'Already registered? Sign in',
    summaryTitle: 'Smart document summary',
    copy: 'Copy',
    copied: 'Copied',
    refresh: 'Refresh',
    history: 'Version history',
    processing: 'AI is analyzing your document...',
    errorBoundary: 'Something went wrong',
    reload: 'Reload',
  },
} as const

export type TranslationKey = keyof (typeof dict)['ru']

let currentLang: Lang = (localStorage.getItem('ai_doc_lang') as Lang) || 'ru'

export function getLang(): Lang {
  return currentLang
}

export function setLang(lang: Lang): void {
  currentLang = lang
  localStorage.setItem('ai_doc_lang', lang)
  window.dispatchEvent(new Event('lang:change'))
}

export function translate(key: TranslationKey): string {
  return dict[currentLang][key] ?? key
}

export function useI18n() {
  const [lang, setLangState] = useState<Lang>(getLang())
  useEffect(() => {
    const onChange = () => setLangState(getLang())
    window.addEventListener('lang:change', onChange)
    return () => window.removeEventListener('lang:change', onChange)
  }, [])
  return { lang, t: translate, setLang }
}
