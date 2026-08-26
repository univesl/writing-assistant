import { useState, useEffect, useRef } from 'react'
import './App.css'
import TopNav from './components/TopNav'
import Sidebar from './components/Sidebar'
import MainContent from './components/MainContent'
import EditorSidebar from './components/EditorSidebar'
import StartPage from './components/StartPage'
import { sessionApi } from './api/sessionApi'
import { writeApi } from './api/writeApi'
import { agentApi } from './api/agentApi'
import { uploadApi } from './api/uploadApi'
import {
  appendKnowledgeSources,
  normalizeOfficialArticleFormat,
  normalizeKnowledgeSourcesInMessage,
} from './utils/generatedOutput'
import { formatSessionTime } from './utils/sessionTime'
import {
  finishSessionTask,
  getSessionTask,
  startSessionTask,
} from './utils/sessionTasks'
import { streamAgentRun } from './services/agentRunStream'

const getGenerationMessage = ({ writingMode, useRag, useWebSearch }) => {
  if (writingMode === 'reference') {
    return '正在解析参考文档并生成公文，请稍候…'
  }
  if (useRag) {
    return useWebSearch ? '正在检索知识库和公开资料并生成公文，请稍候…' : '正在检索知识库并生成公文，请稍候…'
  }
  if (useWebSearch) {
    return '正在检索公开资料并生成公文，请稍候…'
  }
  return '正在生成公文，请稍候…'
}

function App() {
  // 当前选中的会话ID
  const [currentSession, setCurrentSession] = useState(null)
  // 所有会话列表
  const [sessions, setSessions] = useState([])

  // 当前页面：'start' = 开始页面，'content' = 编辑页面
  // 不从 localStorage 恢复，统一从 loadSessionContent 判断
  const [currentPage, setCurrentPage] = useState('start')

  // 当前会话的输出内容（文章主体）
  const [currentSessionOutput, setCurrentSessionOutput] = useState('')

  // 编辑器中的实时内容（用于确保AI使用最新的编辑器内容）
  const [editorRealtimeContent, setEditorRealtimeContent] = useState('')

  // 当前会话的对话历史
  const [currentChatHistory, setCurrentChatHistory] = useState([])

  // 当前会话的引用列表
  const [currentQuotes, setCurrentQuotes] = useState([])

  // 按会话保存正文任务。不同会话可以并行，同一会话只允许一个会改写正文的任务。
  const [sessionTasks, setSessionTasks] = useState({})
  const [agentRuns, setAgentRuns] = useState({})
  const [agentEvents, setAgentEvents] = useState({})

  // 用于跟踪组件是否已挂载，避免竞态条件
  const isMountedRef = useRef(true)
  const isLoadingRef = useRef(false)
  const sessionLoadIdRef = useRef(0)
  const currentSessionIdRef = useRef(null)
  const sessionTasksRef = useRef({})
  const operationCounterRef = useRef(0)
  const agentStreamsRef = useRef(new Map())
  const agentOperationsRef = useRef(new Map())
  const completedAgentRunsRef = useRef(new Set())
  const selectedSessionId = currentSession?.id || null
  const currentTask = getSessionTask(sessionTasks, selectedSessionId)
  const currentAgentRun = selectedSessionId ? agentRuns[String(selectedSessionId)] : null
  const currentAgentEvents = currentAgentRun ? (agentEvents[currentAgentRun.run_id] || []) : []
  const currentAgentActive = ['queued', 'running'].includes(currentAgentRun?.status)
  const activeAgentSessionIds = Object.values(agentRuns)
    .filter(run => ['queued', 'running'].includes(run.status))
    .map(run => run.session_id)
  const activeTaskCount = new Set([
    ...Object.keys(sessionTasks).map(Number),
    ...activeAgentSessionIds,
  ]).size

  const beginSessionTask = (sessionId, kind, message) => {
    const operationId = `${sessionId}-${Date.now()}-${++operationCounterRef.current}`
    const result = startSessionTask(sessionTasksRef.current, sessionId, {
      operationId,
      kind,
      message,
    })
    if (!result) return null

    sessionTasksRef.current = result.tasks
    setSessionTasks(result.tasks)
    return operationId
  }

  const updateSessionTaskMessage = (sessionId, operationId, message) => {
    const key = String(sessionId)
    const current = sessionTasksRef.current[key]
    if (!current || current.operationId !== operationId) return

    const next = {
      ...sessionTasksRef.current,
      [key]: { ...current, message },
    }
    sessionTasksRef.current = next
    setSessionTasks(next)
  }

  const endSessionTask = (sessionId, operationId) => {
    const next = finishSessionTask(sessionTasksRef.current, sessionId, operationId)
    if (next === sessionTasksRef.current) return
    sessionTasksRef.current = next
    setSessionTasks(next)
  }

  const mergeAgentRun = (run) => {
    if (!run?.session_id) return
    setAgentRuns(previous => ({ ...previous, [String(run.session_id)]: run }))
  }

  const finishAgentUi = (run, data = {}, addSummary = true) => {
    const finalRun = {
      ...run,
      status: 'completed',
      current_stage: 'finalize',
      final_article: data.article || run.final_article,
      article_snapshot: data.article || run.article_snapshot,
      summary: data.summary || run.summary,
      references: data.references || run.references || [],
      warnings: data.warnings || run.warnings || [],
      issues: data.issues || run.issues || [],
      outcome: data.outcome || run.outcome || 'document',
      applied_version: data.applied_version ?? run.applied_version,
      activated_skills: data.activated_skills || run.activated_skills || [],
      workflow_plan: data.workflow_plan || run.workflow_plan || {},
    }
    mergeAgentRun(finalRun)
    if (run.session_id === currentSessionIdRef.current && finalRun.final_article) {
      setCurrentSessionOutput(finalRun.final_article)
      setEditorRealtimeContent(finalRun.final_article)
      setCurrentPage('content')
      if (addSummary && finalRun.summary && !completedAgentRunsRef.current.has(run.run_id)) {
        setCurrentChatHistory(previous => [...previous, {
          role: 'assistant',
          content: appendKnowledgeSources(finalRun.summary, finalRun.references),
        }])
      }
    }
    completedAgentRunsRef.current.add(run.run_id)
  }

  const connectAgentRun = (run, operationId = null, { replayOnly = false, after = 0 } = {}) => {
    if (!run?.run_id || agentStreamsRef.current.has(run.run_id)) return
    const controller = new AbortController()
    agentStreamsRef.current.set(run.run_id, controller)
    if (operationId) agentOperationsRef.current.set(run.run_id, operationId)
    let liveRun = run

    streamAgentRun({
      runId: run.run_id,
      after,
      initialArticle: after > 0 ? (run.article_snapshot || '') : '',
      signal: controller.signal,
      onArticle: (article) => {
        const initialDraft = ['quick', 'draft', 'reference', 'reply', 'imitate'].includes(run.task_type)
          && Number(run.base_version || 0) === 0
        if (initialDraft && run.session_id === currentSessionIdRef.current) {
          setCurrentSessionOutput(article)
          setEditorRealtimeContent(article)
          setCurrentPage('content')
        }
      },
      onEvent: (event) => {
        setAgentEvents(previous => {
          const existing = previous[run.run_id] || []
          if (existing.some(item => item.id === event.id)) return previous
          return { ...previous, [run.run_id]: [...existing, event] }
        })
        if (event.type === 'stage.started') {
          liveRun = { ...liveRun, status: 'running', current_stage: event.stage }
          mergeAgentRun(liveRun)
          const op = agentOperationsRef.current.get(run.run_id)
          if (op) updateSessionTaskMessage(run.session_id, op, `Agent 正在执行：${event.data?.label || event.stage}`)
        } else if (event.type === 'run.completed') {
          finishAgentUi(liveRun, event.data, !replayOnly)
        } else if (event.type === 'run.failed' || event.type === 'run.cancelled') {
          liveRun = {
            ...liveRun,
            status: event.type === 'run.failed' ? 'failed' : 'cancelled',
            error: event.data,
          }
          mergeAgentRun(liveRun)
        }
      },
    }).catch(error => {
      if (error.name !== 'AbortError') console.error('Agent 事件流中断:', error)
    }).finally(async () => {
      agentStreamsRef.current.delete(run.run_id)
      try {
        const snapshot = await agentApi.getRun(run.run_id)
        mergeAgentRun(snapshot)
        if (snapshot.status === 'completed') finishAgentUi(snapshot, snapshot, false)
      } catch (error) {
        if (!controller.signal.aborted) console.error('恢复 Agent 状态失败:', error)
      }
      const op = agentOperationsRef.current.get(run.run_id)
      if (op) {
        endSessionTask(run.session_id, op)
        agentOperationsRef.current.delete(run.run_id)
      }
    })
  }

  // 左侧栏显示状态
  const [isSidebarOpen] = useState(() => {
    // 从localStorage恢复侧边栏状态
    const savedState = localStorage.getItem('isSidebarOpen')
    return savedState !== null ? savedState === 'true' : true
  })

  // 加载会话列表
  const loadSessions = async () => {
    // 防止重复调用
    if (isLoadingRef.current) {
      console.log('loadSessions already in progress, skipping')
      return
    }
    isLoadingRef.current = true

    try {
      const response = await sessionApi.getSessions()
      console.log('loadSessions response:', response)

      // 检查组件是否仍然挂载
      if (!isMountedRef.current) {
        console.log('Component unmounted, skipping state update')
        return
      }

      if (response && Array.isArray(response)) {
        const sessionList = response.map(session => ({
          id: session.session_id,
          name: session.session_name,
          createdAt: formatSessionTime(session.created_at)
        }))
        setSessions(sessionList)
        console.log('sessionList:', sessionList)

        // 获取localStorage中保存的当前会话ID
        const savedSessionId = localStorage.getItem('currentSessionId')
        console.log('savedSessionId:', savedSessionId)

        if (sessionList.length > 0) {
          if (savedSessionId) {
            // 查找与保存的ID匹配的会话
            const savedSession = sessionList.find(session => session.id === parseInt(savedSessionId))
            if (savedSession) {
              console.log('Setting currentSession to savedSession:', savedSession)
              setCurrentSession(savedSession)
              return
            }
          }
          // 如果没有保存的会话ID或找不到匹配的会话，默认选中第一个
          console.log('Setting currentSession to first session:', sessionList[0])
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
  }

  // 加载会话内容
  const loadSessionContent = async (sessionId) => {
    const loadId = ++sessionLoadIdRef.current
    setCurrentPage('start')
    setCurrentSessionOutput('')
    setEditorRealtimeContent('')
    setCurrentChatHistory([])

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
        if (latestRun.status === 'completed') completedAgentRunsRef.current.add(latestRun.run_id)
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
      setCurrentSessionOutput('')
      setEditorRealtimeContent('')
      setCurrentChatHistory([])
      setCurrentPage('start')
    }
  }

  // 组件挂载时加载会话列表
  useEffect(() => {
    isMountedRef.current = true
    loadSessions()
    const agentStreams = agentStreamsRef.current
    return () => {
      isMountedRef.current = false
      agentStreams.forEach(controller => controller.abort())
      agentStreams.clear()
    }
  }, [])

  // 当前会话变化时加载会话内容
  useEffect(() => {
    currentSessionIdRef.current = selectedSessionId

    if (selectedSessionId) {
      loadSessionContent(selectedSessionId)
      setCurrentQuotes([])
    } else {
      sessionLoadIdRef.current += 1
      setCurrentPage('start')
      setCurrentSessionOutput('')
      setEditorRealtimeContent('')
      setCurrentChatHistory([])
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
    if (getSessionTask(sessionTasksRef.current, sessionId)) {
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
        console.log('文章内容已保存到后端')
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

  // 处理从 StartPage 发起的生成请求
  const handleStartGeneration = async (config) => {
    if (!currentSession) return
    const generationSessionId = currentSession.id
    const operationId = beginSessionTask(
      generationSessionId,
      'generate',
      getGenerationMessage(config),
    )
    if (!operationId) return
    let agentOwnsTask = false

    try {
      const { writingMode, templateType, quickRequirements, referenceDocuments, referenceWriteType, referenceRequirements, useRag, useWebSearch } = config

      // 构建用户显示内容
      let userDisplayContent = ''
      if (writingMode === 'quick') {
        if (templateType === 'notice') {
          userDisplayContent = quickRequirements ? `写通知：${quickRequirements}` : '写通知'
        } else if (templateType === 'regulation') {
          userDisplayContent = quickRequirements ? `写规章制度：${quickRequirements}` : '写规章制度'
        } else if (templateType === 'speech') {
          userDisplayContent = quickRequirements ? `写讲话稿：${quickRequirements}` : '写讲话稿'
        } else {
          userDisplayContent = quickRequirements ? `写文章：${quickRequirements}` : '写文章'
        }
      } else if (writingMode === 'reference') {
        const uploadDocs = referenceDocuments.filter(d => d.type === 'upload')
        if (uploadDocs.length > 0) {
          const typeLabels = {
            reply: '根据上传文件生成回函',
            imitate: '按结构和风格优先进行智能参考写作',
            general: '智能分析上传文件并生成新文稿'
          }
          userDisplayContent = `${typeLabels[referenceWriteType] || '参考写作'}`
          userDisplayContent += `（共 ${uploadDocs.length} 份参考材料）`
          if (referenceRequirements.trim()) {
            userDisplayContent += `（要求：${referenceRequirements.trim()}）`
          }
        }
      }

      // 保存用户消息到聊天历史
      const newChatHistory = [{
        role: 'user',
        content: userDisplayContent
      }]
      setCurrentChatHistory(newChatHistory)
      writeApi.saveContent(generationSessionId, userDisplayContent, writingMode === 'quick' ? 'quick' : 'reference', 'chat', 'user').catch(() => {})

      if (writingMode === 'quick') {
        setCurrentSessionOutput('')
        setEditorRealtimeContent('')
        setCurrentPage('content')
        updateSessionTaskMessage(generationSessionId, operationId, '正在创建 Agent 运行…')
        const run = await agentApi.createRun({
          session_id: generationSessionId,
          task_type: 'quick',
          document_type: templateType || 'general',
          requirements: quickRequirements || '',
          use_kng: Boolean(useRag),
          use_web_search: Boolean(useWebSearch),
        })
        mergeAgentRun(run)
        setAgentEvents(previous => ({ ...previous, [run.run_id]: [] }))
        connectAgentRun(run, operationId)
        agentOwnsTask = true

      } else if (writingMode === 'reference') {
        const uploadDocs = referenceDocuments.filter(d => d.type === 'upload')
        if (uploadDocs.length === 0) return

        updateSessionTaskMessage(
          generationSessionId,
          operationId,
          `正在解析 ${uploadDocs.length} 份参考材料…`,
        )
        const uploaded = []
        for (const doc of uploadDocs) {
          updateSessionTaskMessage(generationSessionId, operationId, `正在解析：${doc.filename}`)
          uploaded.push(await uploadApi.uploadFile(generationSessionId, doc.file, true, false))
        }
        const sourceFileIds = uploaded.map(item => item.file_id)
        setCurrentSessionOutput('')
        setEditorRealtimeContent('')
        setCurrentPage('content')
        updateSessionTaskMessage(generationSessionId, operationId, '参考材料已解析，正在创建 Agent 运行…')
        const run = await agentApi.createRun({
          session_id: generationSessionId,
          task_type: referenceWriteType === 'general' ? 'reference' : referenceWriteType,
          document_type: templateType || 'general',
          requirements: referenceRequirements.trim(),
          source_file_ids: sourceFileIds,
          use_kng: Boolean(useRag),
          use_web_search: Boolean(useWebSearch),
        })
        mergeAgentRun(run)
        setAgentEvents(previous => ({ ...previous, [run.run_id]: [] }))
        connectAgentRun(run, operationId)
        agentOwnsTask = true
      }
    } catch (error) {
      console.error('生成失败:', error)
      if (generationSessionId === currentSessionIdRef.current) {
        alert('生成失败: ' + (error.message || '未知错误'))
      }
    } finally {
      if (!agentOwnsTask) endSessionTask(generationSessionId, operationId)
    }
  }

  const handleAgentCancel = async (run) => {
    try {
      const updated = await agentApi.cancelRun(run.run_id)
      mergeAgentRun(updated)
    } catch (error) {
      alert(error.message || '取消失败')
    }
  }

  const handleAgentRetry = async (run) => {
    const operationId = beginSessionTask(run.session_id, 'agent-retry', '正在从安全检查点恢复…')
    if (!operationId) return
    try {
      const previousCursor = run.last_event_seq || 0
      completedAgentRunsRef.current.delete(run.run_id)
      const updated = await agentApi.retryRun(run.run_id)
      mergeAgentRun(updated)
      connectAgentRun(updated, operationId, { after: previousCursor })
    } catch (error) {
      endSessionTask(run.session_id, operationId)
      alert(error.message || '重试失败')
    }
  }

  const handleAgentMessage = async (instruction) => {
    if (!currentSession || !instruction.trim()) return
    const sessionId = currentSession.id
    const operationId = beginSessionTask(sessionId, 'agent-message', 'Agent 正在准备修改提案…')
    if (!operationId) return
    const userMessage = { role: 'user', content: instruction.trim() }
    setCurrentChatHistory(previous => [...previous, userMessage])
    writeApi.saveContent(sessionId, userMessage.content, 'quick', 'chat', 'user').catch(() => {})
    try {
      const latestArticle = editorRealtimeContent || currentSessionOutput || ''
      if (latestArticle !== currentSessionOutput) {
        await writeApi.saveArticle(sessionId, latestArticle)
        setCurrentSessionOutput(latestArticle)
      }
      const run = await agentApi.createRun({
        session_id: sessionId,
        task_type: latestArticle.trim() ? 'revise_document' : 'draft',
        document_type: currentAgentRun?.document_type || 'general',
        requirements: instruction.trim(),
        base_article: latestArticle,
        use_kng: false,
      })
      mergeAgentRun(run)
      setAgentEvents(previous => ({ ...previous, [run.run_id]: [] }))
      connectAgentRun(run, operationId)
      return true
    } catch (error) {
      endSessionTask(sessionId, operationId)
      throw error
    }
  }

  const handleAgentSelectionMessage = async ({ instruction, selectedMarkdown, selectionContext, baseArticle }) => {
    if (!currentSession || !instruction.trim() || !selectedMarkdown.trim()) return
    const sessionId = currentSession.id
    const operationId = beginSessionTask(sessionId, 'agent-selection', 'Agent 正在生成选区修改提案…')
    if (!operationId) return
    const userContent = `修改选区：${instruction.trim()}`
    setCurrentChatHistory(previous => [...previous, { role: 'user', content: userContent }])
    writeApi.saveContent(sessionId, userContent, 'quick', 'chat', 'user').catch(() => {})
    try {
      if (baseArticle !== currentSessionOutput) {
        await writeApi.saveArticle(sessionId, baseArticle)
        setCurrentSessionOutput(baseArticle)
      }
      const run = await agentApi.createRun({
        session_id: sessionId,
        task_type: 'revise_selection',
        document_type: currentAgentRun?.document_type || 'general',
        requirements: instruction.trim(),
        base_article: baseArticle,
        selection: { selected_markdown: selectedMarkdown, ...selectionContext },
        use_kng: false,
      })
      mergeAgentRun(run)
      setAgentEvents(previous => ({ ...previous, [run.run_id]: [] }))
      connectAgentRun(run, operationId)
      return true
    } catch (error) {
      endSessionTask(sessionId, operationId)
      throw error
    }
  }

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
