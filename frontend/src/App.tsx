import React, { useState, useEffect } from 'react'
import { BookOpen, MessageSquare, FileText, AlertCircle, LogOut, Files } from 'lucide-react'
import { useDocuments } from './hooks/useDocuments'
import { useDocumentChat } from './hooks/useDocumentChat'
import { useAuth } from './hooks/useAuth'
import { AuthForm } from './components/AuthForm'
import { UserInfo } from './types'
import { Sidebar } from './components/Sidebar'
import { SummaryViewer } from './components/SummaryViewer'
import { ChatPanel } from './components/ChatPanel'
import { PagesViewer } from './components/PagesViewer'
import { useI18n } from './i18n'

type ActiveTab = 'summary' | 'chat' | 'pages'

function MainApp({ user, onLogout }: { user: UserInfo; onLogout: () => void }) {
  const { documents, isLoading, isUploading, error, uploadFile, removeDocument, refresh } =
    useDocuments()

  const [selectedDocId, setSelectedDocId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<ActiveTab>('summary')
  const [focusedPage, setFocusedPage] = useState<number | null>(null)
  const { t } = useI18n()

  useEffect(() => {
    if (!selectedDocId && documents.length > 0) {
      setSelectedDocId(documents[0].id)
    } else if (selectedDocId && !documents.some((d) => d.id === selectedDocId)) {
      setSelectedDocId(documents.length > 0 ? documents[0].id : null)
    }
  }, [documents, selectedDocId])

  const selectedDoc = documents.find((d) => d.id === selectedDocId) || null
  const { messages, isSending, sendMessage, stopGeneration } = useDocumentChat(selectedDocId)

  const handleUpload = async (file: File) => {
    const uploaded = await uploadFile(file)
    if (uploaded) {
      setSelectedDocId(uploaded.id)
      setActiveTab('summary')
    }
  }

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-slate-50 text-slate-900">
      <Sidebar
        documents={documents}
        selectedId={selectedDocId}
        isLoading={isLoading}
        isUploading={isUploading}
        onSelect={(id) => setSelectedDocId(id)}
        onUpload={handleUpload}
        onDelete={removeDocument}
      />

      <main className="flex-1 flex flex-col h-screen overflow-hidden">
        {error && (
          <div className="bg-rose-50 border-b border-rose-200 px-4 py-2.5 text-xs text-rose-700 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!selectedDoc ? (
          <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
            <div className="w-16 h-16 rounded-2xl bg-white border border-slate-200 shadow-xs flex items-center justify-center mb-4">
              <FileText className="w-8 h-8 text-indigo-500" />
            </div>
            <h2 className="text-lg font-semibold text-slate-900">{t('selectDoc')}</h2>
            <p className="text-sm text-slate-500 max-w-md mt-1">{t('selectDocHint')}</p>
          </div>
        ) : (
          <>
            <header className="bg-white border-b border-slate-200 px-6 pt-4">
              <div className="flex items-center justify-between gap-4 mb-3">
                <h2 className="text-base md:text-lg font-semibold text-slate-900 truncate">
                  {selectedDoc.title}
                </h2>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="text-xs text-slate-500 hidden md:inline" title={user.email}>
                    {user.email}
                  </span>
                  <button
                    onClick={onLogout}
                    title="Выйти"
                    aria-label="Выйти"
                    className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-md"
                  >
                    <LogOut className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div className="flex gap-6" role="tablist" aria-label="Document sections">
                <button
                  role="tab"
                  aria-selected={activeTab === 'summary'}
                  onClick={() => setActiveTab('summary')}
                  className={`pb-3 text-sm font-medium border-b-2 transition-colors inline-flex items-center gap-2 ${
                    activeTab === 'summary'
                      ? 'border-indigo-600 text-indigo-600'
                      : 'border-transparent text-slate-500 hover:text-slate-800'
                  }`}
                >
                  <BookOpen className="w-4 h-4" />
                  {t('summaryTab')}
                </button>

                <button
                  role="tab"
                  aria-selected={activeTab === 'chat'}
                  onClick={() => setActiveTab('chat')}
                  className={`pb-3 text-sm font-medium border-b-2 transition-colors inline-flex items-center gap-2 ${
                    activeTab === 'chat'
                      ? 'border-indigo-600 text-indigo-600'
                      : 'border-transparent text-slate-500 hover:text-slate-800'
                  }`}
                >
                  <MessageSquare className="w-4 h-4" />
                  {t('chatTab')}
                </button>

                <button
                  role="tab"
                  aria-selected={activeTab === 'pages'}
                  onClick={() => setActiveTab('pages')}
                  className={`pb-3 text-sm font-medium border-b-2 transition-colors inline-flex items-center gap-2 ${
                    activeTab === 'pages'
                      ? 'border-indigo-600 text-indigo-600'
                      : 'border-transparent text-slate-500 hover:text-slate-800'
                  }`}
                >
                  <Files className="w-4 h-4" />
                  {t('pagesTab')}
                </button>
              </div>
            </header>

            <div className="flex-1 overflow-y-auto">
              {activeTab === 'summary' ? (
                <SummaryViewer document={selectedDoc} onUpdated={refresh} />
              ) : activeTab === 'pages' ? (
                <PagesViewer documentId={selectedDoc.id} focusedPage={focusedPage} />
              ) : (
                <ChatPanel
                  documentTitle={selectedDoc.title}
                  disabled={selectedDoc.status !== 'completed'}
                  messages={messages}
                  isSending={isSending}
                  onSendMessage={sendMessage}
                  onStopGeneration={stopGeneration}
                  onPageClick={(page) => {
                    setFocusedPage(page)
                    setActiveTab('pages')
                  }}
                />
              )}
            </div>
          </>
        )}
      </main>
    </div>
  )
}

export function App() {
  const { user, isLoading, refresh, logout } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-slate-500 text-sm">
        Загрузка...
      </div>
    )
  }

  if (!user) {
    return <AuthForm onAuthenticated={refresh} />
  }

  return <MainApp user={user} onLogout={logout} />
}

export default App
