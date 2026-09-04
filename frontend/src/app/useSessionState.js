import { useRef, useState } from 'react'

export function useSessionState() {
  const [currentSession, setCurrentSession] = useState(null)
  const [sessions, setSessions] = useState([])
  const [currentPage, setCurrentPage] = useState('start')
  const [currentSessionOutput, setCurrentSessionOutput] = useState('')
  const [editorRealtimeContent, setEditorRealtimeContent] = useState('')
  const [currentChatHistory, setCurrentChatHistory] = useState([])
  const [currentQuotes, setCurrentQuotes] = useState([])
  const [isSidebarOpen] = useState(() => {
    const savedState = localStorage.getItem('isSidebarOpen')
    return savedState !== null ? savedState === 'true' : true
  })

  const isMountedRef = useRef(true)
  const isLoadingRef = useRef(false)
  const sessionLoadIdRef = useRef(0)
  const currentSessionIdRef = useRef(null)
  const selectedSessionId = currentSession?.id || null

  const resetSessionView = () => {
    setCurrentPage('start')
    setCurrentSessionOutput('')
    setEditorRealtimeContent('')
    setCurrentChatHistory([])
  }

  return {
    currentChatHistory,
    currentPage,
    currentQuotes,
    currentSession,
    currentSessionIdRef,
    currentSessionOutput,
    editorRealtimeContent,
    isLoadingRef,
    isMountedRef,
    isSidebarOpen,
    resetSessionView,
    selectedSessionId,
    sessionLoadIdRef,
    sessions,
    setCurrentChatHistory,
    setCurrentPage,
    setCurrentQuotes,
    setCurrentSession,
    setCurrentSessionOutput,
    setEditorRealtimeContent,
    setSessions,
  }
}
