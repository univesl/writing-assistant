import { useCallback, useEffect } from 'react'
import '../styles/app.css'
import '../styles/agent.css'
import TopNav from '../components/session/TopNav'
import Sidebar from '../components/session/Sidebar'
import MainContent from '../components/editor/MainContent'
import EditorSidebar from '../components/editor/EditorSidebar'
import StartPage from '../components/start/StartPage'
import { sessionApi } from '../api/sessionApi'
import { writeApi } from '../api/writeApi'
import { agentApi } from '../api/agentApi'
import {
  normalizeOfficialArticleFormat,
  normalizeKnowledgeSourcesInMessage,
} from '../utils/generatedOutput'
import { formatSessionTime } from '../utils/sessionTime'
import { useAgentRuns } from './useAgentRuns'
import { useGenerationFlow } from './useGenerationFlow'
import { useSessionState } from './useSessionState'

function App() {
  const {
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
  } = useSessionState()
  const {
    activeAgentSessionIds,
    activeTaskCount,
    beginSessionTask,
    cancelAgentRun,
    connectAgentRun,
    currentAgentActive,
    currentAgentEvents,
    currentAgentRun,
    currentTask,
    endSessionTask,
    hasActiveSessionTask,
    mergeAgentRun,
    resetAgentEvents,
    retryAgentRun,
    updateSessionTaskMessage,
  } = useAgentRuns({
    selectedSessionId,
    currentSessionIdRef,
    currentSessionOutput,
    setCurrentSessionOutput,
    setEditorRealtimeContent,
    setCurrentPage,
    setCurrentChatHistory,
  })

  // 加载会话列表
  const loadSessions = useCallback(async () => {
    // 防止重复调用
    if (isLoadingRef.current) {
      return
    }
    isLoadingRef.current = true

    try {
      const response = await sessionApi.getSessions()

      // 检查组件是否仍然挂载
      if (!isMountedRef.current) {
        return
      }

      if (response && Array.isArray(response)) {
        const sessionList = response.map(session => ({
          id: session.session_id,
          name: session.session_name,
          createdAt: formatSessionTime(session.created_at)
        }))
        setSessions(sessionList)

        // 获取localStorage中保存的当前会话ID
        const savedSessionId = localStorage.getItem('currentSessionId')

        if (sessionList.length > 0) {
          if (savedSessionId) {
            // 查找与保存的ID匹配的会话
            const savedSession = sessionList.find(session => session.id === parseInt(savedSessionId))
            if (savedSession) {
              setCurrentSession(savedSession)
              return
            }
          }
          // 如果没有保存的会话ID或找不到匹配的会话，默认选中第一个
          setCurrentSession(sessionList[0])
        }
        // 如果没有会话，清空当前会话
        else if (sessionList.length === 0) {
          setCurrentSession(null)
        }
      }
    } catch (error) {
      console.error('加载会话列表失败:', error)
    } finally {
      isLoadingRef.current = false
    }
  }, [isLoadingRef, isMountedRef, setCurrentSession, setSessions])

  // 加载会话内容
  const loadSessionContent = async (sessionId) => {
    const loadId = ++sessionLoadIdRef.current
    resetSessionView()

    try {
      const [articleResponse, chatResponse, runResponse] = await Promise.all([
        writeApi.getArticle(sessionId),
        writeApi.getSessionContent(sessionId),
        agentApi.listRuns(sessionId, 1).catch(() => []),
      ])

      if (!isMountedRef.current || loadId !== sessionLoadIdRef.current) {
        return
      }

      // 旧会话中已经保存的模型 Markdown 也在加载时收敛，避免用户必须重新
      // 生成才能看到公文编号格式；正式的“一、”“1、”“第一条”“（一）”会保留。
      const articleText = normalizeOfficialArticleFormat(articleResponse?.article_content || '')
      const hasArticle = articleText.trim().length > 0

      const latestRun = runResponse?.[0] || null
      const initialTask = latestRun && ['quick', 'draft', 'reference', 'reply', 'imitate'].includes(latestRun.task_type)
        && Number(latestRun.base_version || 0) === 0
      const recoverableDraft = latestRun && initialTask && ['queued', 'running'].includes(latestRun.status)
        ? normalizeOfficialArticleFormat(latestRun.article_snapshot || '')
        : ''
      const visibleArticle = recoverableDraft || (hasArticle ? articleText : '')
      setCurrentSessionOutput(visibleArticle)
      setEditorRealtimeContent(visibleArticle)
      setCurrentPage(visibleArticle.trim() ? 'content' : 'start')

      if (latestRun) {
        mergeAgentRun(latestRun)
        connectAgentRun(latestRun, null, { replayOnly: true })
      }

      if (chatResponse && chatResponse.length > 0) {
        setCurrentChatHistory(chatResponse.map(item => ({
          role: item.role,
          content: normalizeKnowledgeSourcesInMessage(item.content)
        })))
      } else {
        setCurrentChatHistory([])
      }
    } catch (error) {
      if (loadId !== sessionLoadIdRef.current) {
        return
      }
      console.error('加载会话内容失败:', error)
      resetSessionView()
    }
  }

  // 组件挂载时加载会话列表
  useEffect(() => {
    isMountedRef.current = true
    loadSessions()
    return () => {
      isMountedRef.current = false
    }
  }, [isMountedRef, loadSessions])

  // 当前会话变化时加载会话内容
  useEffect(() => {
    currentSessionIdRef.current = selectedSessionId

    if (selectedSessionId) {
      loadSessionContent(selectedSessionId)
      setCurrentQuotes([])
    } else {
      sessionLoadIdRef.current += 1
      resetSessionView()
      setCurrentQuotes([])
    }
  // loadSessionContent intentionally reads the latest refs while the session id is the trigger.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSessionId])

  // 保存侧边栏状态到localStorage
  useEffect(() => {
    localStorage.setItem('isSidebarOpen', isSidebarOpen)
  }, [isSidebarOpen])

  // 处理新建会话
  const handleNewSession = async () => {
    try {
      // 调用后端API创建新会话
      const response = await sessionApi.createSession('新会话')
      const newSession = {
        id: response.session_id,
        name: response.session_name,
        createdAt: formatSessionTime(response.created_at)
      }

      // 更新会话列表
      setSessions([newSession, ...sessions])

      // 设置当前会话为新创建的会话
      sessionLoadIdRef.current += 1
      currentSessionIdRef.current = newSession.id
      setCurrentSession(newSession)
      // 保存当前会话ID到localStorage
      localStorage.setItem('currentSessionId', newSession.id)
      // 切换到开始页面
      setCurrentPage('start')
    } catch (error) {
      console.error('创建会话失败:', error)
      // 失败时使用本地模拟数据
      const mockSession = {
        id: Date.now(),
        name: '新会话',
        createdAt: formatSessionTime(new Date())
      }
      setSessions([mockSession, ...sessions])
      sessionLoadIdRef.current += 1
      currentSessionIdRef.current = mockSession.id
      setCurrentSession(mockSession)
      // 保存当前会话ID到localStorage
      localStorage.setItem('currentSessionId', mockSession.id)
      setCurrentPage('start')
    }
  }

  // 处理删除会话
  const handleDeleteSession = async (sessionId) => {
    if (hasActiveSessionTask(sessionId)) {
      alert('该会话仍有任务运行，完成后再删除')
      return
    }

    try {
      // 调用后端API删除会话
      await sessionApi.deleteSession(sessionId)

      // 更新会话列表
      const updatedSessions = sessions.filter(session => session.id !== sessionId)
      setSessions(updatedSessions)

      // 如果删除的是当前会话，设置新的当前会话
      if (currentSession.id === sessionId) {
        if (updatedSessions.length > 0) {
          sessionLoadIdRef.current += 1
          currentSessionIdRef.current = updatedSessions[0].id
          setCurrentSession(updatedSessions[0])
          // 保存新的当前会话ID到localStorage
          localStorage.setItem('currentSessionId', updatedSessions[0].id)
          setCurrentPage('start')
        } else {
          // 如果删除了最后一个会话，清空当前会话
          sessionLoadIdRef.current += 1
          currentSessionIdRef.current = null
          setCurrentSession(null)
          // 从localStorage中删除当前会话ID
          localStorage.removeItem('currentSessionId')
          setCurrentPage('start')
        }
      }
    } catch (error) {
      console.error('删除会话失败:', error)
      // 失败时使用本地模拟删除
      const updatedSessions = sessions.filter(session => session.id !== sessionId)
      setSessions(updatedSessions)

      if (currentSession.id === sessionId) {
        if (updatedSessions.length > 0) {
          sessionLoadIdRef.current += 1
          currentSessionIdRef.current = updatedSessions[0].id
          setCurrentSession(updatedSessions[0])
          // 保存新的当前会话ID到localStorage
          localStorage.setItem('currentSessionId', updatedSessions[0].id)
          setCurrentPage('start')
        } else {
          // 如果删除了最后一个会话，清空当前会话
          sessionLoadIdRef.current += 1
          currentSessionIdRef.current = null
          setCurrentSession(null)
          // 从localStorage中删除当前会话ID
          localStorage.removeItem('currentSessionId')
          setCurrentPage('start')
        }
      }
    }
  }

  // 处理重命名会话
  const handleRenameSession = async (sessionId, newName) => {
    try {
      // 调用后端API重命名会话
      await sessionApi.renameSession(sessionId, newName)

      // 更新会话列表
      const updatedSessions = sessions.map(session => {
        if (session.id === sessionId) {
          return { ...session, name: newName }
        }
        return session
      })
      setSessions(updatedSessions)

      // 如果重命名的是当前会话，更新当前会话
      if (currentSession.id === sessionId) {
        setCurrentSession({ ...currentSession, name: newName })
      }
    } catch (error) {
      console.error('重命名会话失败:', error)
      // 失败时使用本地模拟重命名
      const updatedSessions = sessions.map(session => {
        if (session.id === sessionId) {
          return { ...session, name: newName }
        }
        return session
      })
      setSessions(updatedSessions)

      if (currentSession.id === sessionId) {
        setCurrentSession({ ...currentSession, name: newName })
      }
    }
  }

  // 处理会话切换
  const handleSessionChange = (session) => {
    sessionLoadIdRef.current += 1
    currentSessionIdRef.current = session.id
    setCurrentSession(session)
    localStorage.setItem('currentSessionId', session.id)
    // 切换会话时立即回到开始页面，等 loadSessionContent 确定有无内容
    setCurrentPage('start')
  }

  // 处理文章内容更新
  const handleArticleUpdate = async (sessionId, content, options = {}) => {
    const { persist = true } = options
    if (sessionId === currentSessionIdRef.current) {
      setCurrentSessionOutput(content)
      setEditorRealtimeContent(content)
      if (!persist) return

      try {
        await writeApi.saveArticle(sessionId, content)
      } catch (error) {
        console.error('保存文章内容失败:', error)
      }
    }
  }

  // 处理对话历史更新
  const handleChatHistoryUpdate = (sessionId, chatHistory) => {
    if (sessionId === currentSessionIdRef.current) {
      setCurrentChatHistory(chatHistory)
    }
  }

  // 处理添加引用
  const handleAddQuote = (text, matchResult) => {
    const newQuote = {
      id: Date.now(),
      text: text,
      preview: text.length > 30 ? text.substring(0, 30) + '...' : text,
      match: matchResult
    }
    setCurrentQuotes(prev => [...prev, newQuote])
  }

  // 处理删除引用
  const handleRemoveQuote = (quoteId) => {
    setCurrentQuotes(prev => prev.filter(q => q.id !== quoteId))
  }

  // 处理清空引用
  const handleClearQuotes = () => {
    setCurrentQuotes([])
  }

  // 处理编辑器内容实时变化
  const handleEditorContentChange = (sessionId, content) => {
    if (sessionId === currentSessionIdRef.current) {
      setEditorRealtimeContent(content)
    }
  }

  const {
    cancelRun: handleAgentCancel,
    retryRun: handleAgentRetry,
    sendAgentMessage: handleAgentMessage,
    sendAgentSelectionMessage: handleAgentSelectionMessage,
    startGeneration: handleStartGeneration,
  } = useGenerationFlow({
    currentAgentRun,
    currentSession,
    currentSessionIdRef,
    currentSessionOutput,
    editorRealtimeContent,
    beginSessionTask,
    cancelAgentRun,
    connectAgentRun,
    endSessionTask,
    mergeAgentRun,
    resetAgentEvents,
    retryAgentRun,
    setCurrentChatHistory,
    setCurrentPage,
    setCurrentSessionOutput,
    setEditorRealtimeContent,
    updateSessionTaskMessage,
  })

  return (
    <div className="app-container">
      <TopNav />
      {activeTaskCount > 0 && (
        <div
          className="generation-status"
          role="status"
          aria-live="polite"
          aria-atomic="true"
          data-testid="generation-status"
        >
          <span className="generation-status-spinner" aria-hidden="true" />
          <div className="generation-status-copy">
            <strong>
              {activeTaskCount > 1 ? `正在处理 ${activeTaskCount} 个会话` : '正在处理'}
            </strong>
            <span>{currentTask?.message || (currentAgentActive ? 'Agent 正在后台处理当前正文…' : '其他会话正在后台处理…')}</span>
          </div>
        </div>
      )}
      <div className={`main-layout ${isSidebarOpen ? '' : 'sidebar-closed'}`}>
        <Sidebar
          sessions={sessions}
          currentSession={currentSession}
          onSessionChange={handleSessionChange}
          onNewSession={handleNewSession}
          onDeleteSession={handleDeleteSession}
          onRenameSession={handleRenameSession}
          isOpen={isSidebarOpen}
          activeRunSessionIds={activeAgentSessionIds}
        />
        {currentSession ? (
          currentPage === 'start' ? (
            <StartPage
              key={`start-${currentSession.id}`}
              currentSession={currentSession}
              onGenerate={handleStartGeneration}
              isGenerating={Boolean(currentTask) || currentAgentActive}
            />
          ) : (
            <>
              <MainContent
                key={`main-${currentSession.id}`}
                currentSession={currentSession}
                currentOutput={currentSessionOutput}
                editorContent={editorRealtimeContent}
                chatHistory={currentChatHistory}
                onArticleUpdate={handleArticleUpdate}
                onChatHistoryUpdate={handleChatHistoryUpdate}
                quotes={currentQuotes}
                onRemoveQuote={handleRemoveQuote}
                onClearQuotes={handleClearQuotes}
                isBusy={Boolean(currentTask) || currentAgentActive}
                onTaskStart={beginSessionTask}
                onTaskFinish={endSessionTask}
                agentRun={currentAgentRun}
                agentEvents={currentAgentEvents}
                onAgentCancel={handleAgentCancel}
                onAgentRetry={handleAgentRetry}
                onAgentMessage={handleAgentMessage}
              />
              <EditorSidebar
                key={`editor-${currentSession.id}`}
                currentSession={currentSession}
                currentOutput={currentSessionOutput}
                onArticleUpdate={handleArticleUpdate}
                onAddQuote={handleAddQuote}
                onEditorContentChange={handleEditorContentChange}
                chatHistory={currentChatHistory}
                onChatHistoryUpdate={handleChatHistoryUpdate}
                isBusy={Boolean(currentTask) || currentAgentActive}
                onTaskStart={beginSessionTask}
                onTaskFinish={endSessionTask}
                isSessionActive={(sessionId) => sessionId === currentSessionIdRef.current}
                onAgentSelectionMessage={handleAgentSelectionMessage}
              />
            </>
          )
        ) : (
          <div className="empty-session-message">
            请创建会话
          </div>
        )}
      </div>
    </div>
  )
}

export default App
