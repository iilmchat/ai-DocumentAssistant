import React, { useState } from 'react'
import { Sparkles, LogIn, UserPlus, Loader2, AlertCircle } from 'lucide-react'
import { apiClient, tokenStore } from '../api/client'
import { useI18n } from '../i18n'

interface AuthFormProps {
  onAuthenticated: () => void
}

export const AuthForm: React.FC<AuthFormProps> = ({ onAuthenticated }) => {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { t, lang, setLang } = useI18n()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      const result =
        mode === 'login'
          ? await apiClient.login(email, password)
          : await apiClient.register(email, password)
      tokenStore.setPair(result)
      onAuthenticated()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка авторизации')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-sm border border-slate-200 p-8">
        <div className="flex items-center gap-2.5 mb-6">
          <div className="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center text-white">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-semibold text-slate-900">{t('appName')}</h1>
            <p className="text-xs text-slate-500">{t('appSubtitle')}</p>
          </div>
          <button
            type="button"
            onClick={() => setLang(lang === 'ru' ? 'en' : 'ru')}
            aria-label="Switch language"
            className="ml-auto text-xs font-semibold text-indigo-600 border border-indigo-200 rounded px-2 py-1"
          >
            {lang.toUpperCase()}
          </button>
        </div>

        <h2 className="text-lg font-semibold text-slate-900 mb-1">
          {mode === 'login' ? t('loginTitle') : t('registerTitle')}
        </h2>
        <p className="text-sm text-slate-500 mb-5">
          {mode === 'login'
            ? 'Войдите, чтобы получить доступ к своим документам'
            : 'Регистрация займёт меньше минуты'}
        </p>

        {error && (
          <div className="flex items-center gap-2 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2 mb-4">
            <AlertCircle className="w-4 h-4 shrink-0" /> {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">
              {t('password')}
            </label>
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Не менее 6 символов"
              className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500"
            />
          </div>
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white font-medium py-2.5 rounded-lg text-sm"
          >
            {isSubmitting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : mode === 'login' ? (
              <LogIn className="w-4 h-4" />
            ) : (
              <UserPlus className="w-4 h-4" />
            )}
            {mode === 'login' ? t('login') : t('register')}
          </button>
        </form>

        <button
          onClick={() => {
            setMode(mode === 'login' ? 'register' : 'login')
            setError(null)
          }}
          className="w-full mt-4 text-sm text-indigo-600 hover:text-indigo-700"
        >
          {mode === 'login' ? t('toRegister') : t('toLogin')}
        </button>
      </div>
    </div>
  )
}
