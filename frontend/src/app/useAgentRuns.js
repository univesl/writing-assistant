import { useEffect, useRef, useState } from 'react'
import { agentApi } from '../api/agentApi'
import { appendKnowledgeSources } from '../utils/generatedOutput'
import {
  finishSessionTask,
  getSessionTask,
  startSessionTask,
} from '../utils/sessionTasks'
import {
  canStreamArticleToEditor,
  completeAgentRun,
  isActiveAgentRun,
  shouldApplyRunArticleToEditor,
} from '../utils/agentRun'
import { streamAgentRun } from '../services/agentRunStream'

export function useAgentRuns({
  selectedSessionId,
  currentSessionIdRef,
  currentSessionOutput,
  setCurrentSessionOutput,
  setEditorRealtimeContent,
  setCurrentPage,
  setCurrentChatHistory,
}) {
  const [sessionTasks, setSessionTasks] = useState({})
  const [agentRuns, setAgentRuns] = useState({})
  const [agentEvents, setAgentEvents] = useState({})

  const sessionTasksRef = useRef({})
  const operationCounterRef = useRef(0)
  const agentStreamsRef = useRef(new Map())
  const agentOperationsRef = useRef(new Map())
  const completedAgentRunsRef = useRef(new Set())

  useEffect(() => {
    const streams = agentStreamsRef.current
    return () => {
      streams.forEach(controller => controller.abort())
      streams.clear()
    }
  }, [])

  const currentTask = getSessionTask(sessionTasks, selectedSessionId)
  const currentAgentRun = selectedSessionId ? agentRuns[String(selectedSessionId)] : null
  const currentAgentEvents = currentAgentRun ? (agentEvents[currentAgentRun.run_id] || []) : []
  const currentAgentActive = isActiveAgentRun(currentAgentRun)
  const activeAgentSessionIds = Object.values(agentRuns)
    .filter(isActiveAgentRun)
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
    const finalRun = completeAgentRun(run, data)
    mergeAgentRun(finalRun)
    if (run.session_id === currentSessionIdRef.current && shouldApplyRunArticleToEditor(finalRun)) {
      setCurrentSessionOutput(finalRun.final_article)
      setEditorRealtimeContent(finalRun.final_article)
      setCurrentPage('content')
    } else if (run.session_id === currentSessionIdRef.current && finalRun.outcome === 'proposal') {
      setCurrentSessionOutput(data.articleBeforeRun || '')
      setEditorRealtimeContent(data.articleBeforeRun || '')
      setCurrentPage((data.articleBeforeRun || '').trim() ? 'content' : 'start')
    }
    if (run.session_id === currentSessionIdRef.current) {
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
    const articleBeforeRun = run.session_id === currentSessionIdRef.current ? currentSessionOutput : ''

    streamAgentRun({
      runId: run.run_id,
      after,
      initialArticle: after > 0 ? (run.article_snapshot || '') : '',
      signal: controller.signal,
      onArticle: (article) => {
        if (canStreamArticleToEditor(run) && run.session_id === currentSessionIdRef.current) {
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
          finishAgentUi(liveRun, { ...event.data, articleBeforeRun }, !replayOnly)
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
        if (snapshot.status === 'completed') finishAgentUi(snapshot, { ...snapshot, articleBeforeRun }, false)
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

  const cancelAgentRun = async (run) => {
    const updated = await agentApi.cancelRun(run.run_id)
    mergeAgentRun(updated)
  }

  const retryAgentRun = async (run) => {
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
      throw error
    }
  }

  const resetAgentEvents = (runId) => {
    setAgentEvents(previous => ({ ...previous, [runId]: [] }))
  }

  const hasActiveSessionTask = (sessionId) => {
    return Boolean(getSessionTask(sessionTasksRef.current, sessionId) || isActiveAgentRun(agentRuns[String(sessionId)]))
  }

  return {
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
  }
}
