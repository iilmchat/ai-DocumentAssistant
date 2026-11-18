import React from 'react'
import { AlertTriangle } from 'lucide-react'

interface State {
  hasError: boolean
  message?: string
}

export class ErrorBoundary extends React.Component<{ children: React.ReactNode }, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div role="alert" className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
          <div className="max-w-md bg-white border border-rose-200 rounded-xl p-8 text-center">
            <AlertTriangle className="w-8 h-8 text-rose-500 mx-auto mb-3" />
            <h1 className="text-lg font-semibold text-slate-900">Что-то пошло не так</h1>
            <p className="text-sm text-slate-500 mt-2">{this.state.message}</p>
            <button
              onClick={() => window.location.reload()}
              className="mt-5 bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm"
            >
              Перезагрузить
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
