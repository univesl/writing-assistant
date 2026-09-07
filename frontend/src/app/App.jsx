import { useCallback, useEffect, useRef, useState } from 'react'
import '../styles/app.css'
import '../styles/agent.css'
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

const PANEL_WIDTHS = {
  sidebar: { min: 180, max: 360, default: 240 },
  editor: { min: 320, defaultRatio: 0.52 },
}
const MIN_MAIN_CONTENT_WIDTH = 360
const RESIZE_HANDLE_WIDTH = 16

const getEditorBounds = (
  viewportWidth = window.innerWidth,
  availableMax = Number.POSITIVE_INFINITY,
) => {
  const min = Math.max(PANEL_WIDTHS.editor.min, Math.round(viewportWidth / 3))
  const ratioMax = Math.round(viewportWidth * 0.6)
  const max = Math.max(min, Math.min(ratioMax, availableMax))
  return { min, max }
}

const getDefaultEditorWidth = (viewportWidth = window.innerWidth, sidebarWidth = PANEL_WIDTHS.sidebar.default) => {
  const availableMax = viewportWidth - sidebarWidth - MIN_MAIN_CONTENT_WIDTH - RESIZE_HANDLE_WIDTH
  const bounds = getEditorBounds(viewportWidth, availableMax)
  return Math.round(Math.min(bounds.max, Math.max(bounds.min, viewportWidth * PANEL_WIDTHS.editor.defaultRatio)))
}

const readPanelWidth = (storageKey, panelKey, fallback, availableMax = Number.POSITIVE_INFINITY) => {
  const value = Number(window.localStorage.getItem(storageKey))
  if (!Number.isFinite(value)) return fallback
  if (panelKey === 'editor' && [360, 520].includes(value)) return fallback
  const bounds = panelKey === 'editor' ? getEditorBounds(window.innerWidth, availableMax) : PANEL_WIDTHS[panelKey]
  return Math.min(bounds.max, Math.max(bounds.min, value))
}

const clampPanelWidth = (value, key, availableMax, viewportWidth = window.innerWidth) => {
  const bounds = key === 'editor'
    ? getEditorBounds(viewportWidth, availableMax)
    : PANEL_WIDTHS[key]
  const max = Math.max(bounds.min, Math.min(bounds.max, availableMax))
  return Math.round(Math.min(max, Math.max(bounds.min, value)))
}

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

  const [sidebarWidth, setSidebarWidth] = useState(() => readPanelWidth('sidebarWidth', 'sidebar', PANEL_WIDTHS.sidebar.default))
  const [editorPanelWidth, setEditorPanelWidth] = useState(() => {
    const initialSidebarWidth = readPanelWidth('sidebarWidth', 'sidebar', PANEL_WIDTHS.sidebar.default)
    const availableMax = window.innerWidth - initialSidebarWidth - MIN_MAIN_CONTENT_WIDTH - RESIZE_HANDLE_WIDTH
    return readPanelWidth(
      'editorPanelWidth',
      'editor',
      getDefaultEditorWidth(window.innerWidth, initialSidebarWidth),
      availableMax,
    )
  })
  const layoutRef = useRef(null)
  const panelResizeRef = useRef(null)
  const sidebarWidthRef = useRef(sidebarWidth)
  const editorPanelWidthRef = useRef(editorPanelWidth)
  const layoutWidth = window.innerWidth
  const availableEditorMax = layoutWidth - sidebarWidth - MIN_MAIN_CONTENT_WIDTH - RESIZE_HANDLE_WIDTH
  const editorBounds = getEditorBounds(layoutWidth, availableEditorMax)
  const effectiveEditorPanelWidth = clampPanelWidth(
    editorPanelWidth,
    'editor',
    availableEditorMax,
    layoutWidth,
  )

  useEffect(() => {
    sidebarWidthRef.current = sidebarWidth
    window.localStorage.setItem('sidebarWidth', String(sidebarWidth))
  }, [sidebarWidth])

  useEffect(() => {
    editorPanelWidthRef.current = editorPanelWidth
    window.localStorage.setItem('editorPanelWidth', String(editorPanelWidth))
  }, [editorPanelWidth])

  useEffect(() => {
    const nextWidth = clampPanelWidth(
      editorPanelWidth,
      'editor',
      window.innerWidth - sidebarWidth - MIN_MAIN_CONTENT_WIDTH - RESIZE_HANDLE_WIDTH,
      window.innerWidth,
    )
    if (nextWidth !== editorPanelWidth) {
      setEditorPanelWidth(nextWidth)
    }
  }, [editorPanelWidth, sidebarWidth])

  const startPanelResize = (panel, event) => {
    if (window.innerWidth <= 768) return
    event.preventDefault()
    panelResizeRef.current = {
      panel,
      startX: event.clientX,
      startWidth: panel === 'sidebar' ? sidebarWidthRef.current : editorPanelWidthRef.current,
    }
    event.currentTarget.setPointerCapture?.(event.pointerId)
    document.body.classList.add('panel-resizing')
  }

  const resetPanelWidth = (panel) => {
    if (panel === 'sidebar') {
      setSidebarWidth(PANEL_WIDTHS.sidebar.default)
    } else {
      setEditorPanelWidth(getDefaultEditorWidth(window.innerWidth, sidebarWidthRef.current))
    }
  }

  useEffect(() => {
    const handlePointerMove = (event) => {
      const resize = panelResizeRef.current
      if (!resize) return

      const layoutWidth = layoutRef.current?.getBoundingClientRect().width || window.innerWidth
      const availableForPanel = layoutWidth - MIN_MAIN_CONTENT_WIDTH - RESIZE_HANDLE_WIDTH
      const delta = event.clientX - resize.startX

      if (resize.panel === 'sidebar') {
        const maxWidth = availableForPanel - editorPanelWidthRef.current
        setSidebarWidth(clampPanelWidth(resize.startWidth + delta, 'sidebar', maxWidth))
      } else {
        const maxWidth = availableForPanel - sidebarWidthRef.current
        setEditorPanelWidth(clampPanelWidth(resize.startWidth - delta, 'editor', maxWidth, layoutWidth))
      }
    }

    const stopPanelResize = () => {
      if (!panelResizeRef.current) return
      panelResizeRef.current = null
      document.body.classList.remove('panel-resizing')
    }

    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', stopPanelResize)
    window.addEventListener('pointercancel', stopPanelResize)
    return () => {
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerup', stopPanelResize)
      window.removeEventListener('pointercancel', stopPanelResize)
      document.body.classList.remove('panel-resizing')
    }
  }, [])

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
      <div ref={layoutRef} className={`main-layout ${isSidebarOpen ? '' : 'sidebar-closed'}`}>
        <Sidebar
          sessions={sessions}
          currentSession={currentSession}
          onSessionChange={handleSessionChange}
          onNewSession={handleNewSession}
          onDeleteSession={handleDeleteSession}
          onRenameSession={handleRenameSession}
          isOpen={isSidebarOpen}
          activeRunSessionIds={activeAgentSessionIds}
          style={{ '--sidebar-width': `${sidebarWidth}px` }}
        />
        {isSidebarOpen && (
          <div
            className="panel-resize-handle sidebar-panel-resizer"
            role="separator"
            aria-orientation="vertical"
            aria-label="调整会话栏宽度"
            aria-valuemin={PANEL_WIDTHS.sidebar.min}
            aria-valuemax={PANEL_WIDTHS.sidebar.max}
            aria-valuenow={sidebarWidth}
            onPointerDown={(event) => startPanelResize('sidebar', event)}
            onDoubleClick={() => resetPanelWidth('sidebar')}
            title="拖动调整会话栏宽度，双击恢复默认"
          />
        )}
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
              <div
                className="panel-resize-handle editor-panel-resizer"
                role="separator"
                aria-orientation="vertical"
                aria-label="调整对话栏和编辑器宽度"
                aria-valuemin={editorBounds.min}
                aria-valuemax={editorBounds.max}
                aria-valuenow={effectiveEditorPanelWidth}
                onPointerDown={(event) => startPanelResize('editor', event)}
                onDoubleClick={() => resetPanelWidth('editor')}
                title="拖动调整编辑器宽度，双击恢复默认"
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
                style={{ '--editor-width': `${effectiveEditorPanelWidth}px` }}
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
