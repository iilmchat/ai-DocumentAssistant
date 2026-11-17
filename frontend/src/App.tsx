import React, { useState, useEffect } from 'react';
import { BookOpen, MessageSquare, FileText, AlertCircle } from 'lucide-react';
import { useDocuments } from './hooks/useDocuments';
import { useDocumentChat } from './hooks/useDocumentChat';
import { Sidebar } from './components/Sidebar';
import { SummaryViewer } from './components/SummaryViewer';
import { ChatPanel } from './components/ChatPanel';

type ActiveTab = 'summary' | 'chat';

export function App() {
  const {
    documents,
    isLoading,
    isUploading,
    error,
    uploadFile,
    removeDocument,
  } = useDocuments();

  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>('summary');

  useEffect(() => {
    if (!selectedDocId && documents.length > 0) {
      setSelectedDocId(documents[0].id);
    } else if (selectedDocId && !documents.some((d) => d.id === selectedDocId)) {
      setSelectedDocId(documents.length > 0 ? documents[0].id : null);
    }
  }, [documents, selectedDocId]);

  const selectedDoc = documents.find((d) => d.id === selectedDocId) || null;
  const { messages, isSending, sendMessage, stopGeneration } = useDocumentChat(selectedDocId);

  const handleUpload = async (file: File) => {
    const uploaded = await uploadFile(file);
    if (uploaded) {
      setSelectedDocId(uploaded.id);
      setActiveTab('summary');
    }
  };

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-slate-50 text-slate-900">
      {/* Боковая панель со списком документов */}
      <Sidebar
        documents={documents}
        selectedId={selectedDocId}
        isLoading={isLoading}
        isUploading={isUploading}
        onSelect={(id) => setSelectedDocId(id)}
        onUpload={handleUpload}
        onDelete={removeDocument}
      />

      {/* Основная рабочая область */}
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
            <h2 className="text-lg font-semibold text-slate-900">
              Выберите или загрузите документ
            </h2>
            <p className="text-sm text-slate-500 max-w-md mt-1">
              Загрузите PDF, DOCX или TXT файл в меню слева, чтобы автоматически получить его умный конспект и задать вопросы в RAG-чате.
            </p>
          </div>
        ) : (
          <>
            {/* Верхняя панель активного документа и вкладки */}
            <header className="bg-white border-b border-slate-200 px-6 pt-4">
              <div className="flex items-center justify-between gap-4 mb-3">
                <h2 className="text-base md:text-lg font-semibold text-slate-900 truncate">
                  {selectedDoc.title}
                </h2>
              </div>

              <div className="flex gap-6">
                <button
                  onClick={() => setActiveTab('summary')}
                  className={`pb-3 text-sm font-medium border-b-2 transition-colors inline-flex items-center gap-2 ${
                    activeTab === 'summary'
                      ? 'border-indigo-600 text-indigo-600'
                      : 'border-transparent text-slate-500 hover:text-slate-800'
                  }`}
                >
                  <BookOpen className="w-4 h-4" />
                  Умный конспект
                </button>

                <button
                  onClick={() => setActiveTab('chat')}
                  className={`pb-3 text-sm font-medium border-b-2 transition-colors inline-flex items-center gap-2 ${
                    activeTab === 'chat'
                      ? 'border-indigo-600 text-indigo-600'
                      : 'border-transparent text-slate-500 hover:text-slate-800'
                  }`}
                >
                  <MessageSquare className="w-4 h-4" />
                  Чат по документу
                </button>
              </div>
            </header>

            {/* Контент активной вкладки */}
            <div className="flex-1 overflow-y-auto">
              {activeTab === 'summary' ? (
                <SummaryViewer document={selectedDoc} />
              ) : (
                <ChatPanel
                  documentTitle={selectedDoc.title}
                  disabled={selectedDoc.status !== 'completed'}
                  messages={messages}
                  isSending={isSending}
                  onSendMessage={sendMessage}
                  onStopGeneration={stopGeneration}
                />
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

export default App;
