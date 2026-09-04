import { agentApi } from '../api/agentApi'
import { uploadApi } from '../api/uploadApi'
import { writeApi } from '../api/writeApi'

const getGenerationMessage = ({ writingMode, referenceWriteType, useRag, useWebSearch }) => {
  if (writingMode === 'reference') {
    if (referenceWriteType === 'reply') return '正在解析来文并生成回函，请稍候…'
    if (referenceWriteType === 'imitate') return '正在解析主底稿并进行微调，请稍候…'
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

function buildUserDisplayContent(config) {
  const {
    writingMode,
    templateType,
    quickRequirements,
    referenceDocuments,
    referenceWriteType,
    referenceRequirements,
  } = config

  if (writingMode === 'quick') {
    const typeLabels = {
      notice: '写通知',
      regulation: '写规章制度',
      speech: '写讲话稿',
    }
    const label = typeLabels[templateType] || '写文章'
    return quickRequirements ? `${label}：${quickRequirements}` : label
  }

  if (writingMode === 'reference') {
    const uploadDocs = referenceDocuments.filter(doc => doc.type === 'upload')
    if (!uploadDocs.length) return ''
    const typeLabels = {
      reply: '根据上传文件生成回函',
      imitate: '根据上传文件进行底稿微调',
      reference: '智能分析上传文件并生成新文稿',
    }
    const label = typeLabels[referenceWriteType] || '参考写作'
    const requirementText = referenceRequirements.trim()
    return `${label}（共 ${uploadDocs.length} 份参考材料）${requirementText ? `（要求：${requirementText}）` : ''}`
  }

  return ''
}

export function useGenerationFlow({
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
}) {
  const startGeneration = async (config) => {
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
      const {
        writingMode,
        templateType,
        quickRequirements,
        referenceDocuments,
        referenceWriteType,
        referenceRequirements,
        useRag,
        useWebSearch,
      } = config
      const userDisplayContent = buildUserDisplayContent(config)

      setCurrentChatHistory([{ role: 'user', content: userDisplayContent }])
      writeApi
        .saveContent(
          generationSessionId,
          userDisplayContent,
          writingMode === 'quick' ? 'quick' : 'reference',
          'chat',
          'user',
        )
        .catch(() => {})

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
        resetAgentEvents(run.run_id)
        connectAgentRun(run, operationId)
        agentOwnsTask = true
      } else if (writingMode === 'reference') {
        const uploadDocs = referenceDocuments.filter(doc => doc.type === 'upload')
        if (uploadDocs.length === 0) return

        updateSessionTaskMessage(generationSessionId, operationId, `正在解析 ${uploadDocs.length} 份参考材料…`)
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
          task_type: referenceWriteType,
          document_type: templateType || 'general',
          requirements: referenceRequirements.trim(),
          source_file_ids: sourceFileIds,
          use_kng: Boolean(useRag),
          use_web_search: Boolean(useWebSearch),
        })
        mergeAgentRun(run)
        resetAgentEvents(run.run_id)
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

  const cancelRun = async (run) => {
    try {
      await cancelAgentRun(run)
    } catch (error) {
      alert(error.message || '取消失败')
    }
  }

  const retryRun = async (run) => {
    try {
      await retryAgentRun(run)
    } catch (error) {
      alert(error.message || '重试失败')
    }
  }

  const sendAgentMessage = async (instruction) => {
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
      resetAgentEvents(run.run_id)
      connectAgentRun(run, operationId)
      return true
    } catch (error) {
      endSessionTask(sessionId, operationId)
      throw error
    }
  }

  const sendAgentSelectionMessage = async ({ instruction, selectedMarkdown, selectionContext, baseArticle }) => {
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
      resetAgentEvents(run.run_id)
      connectAgentRun(run, operationId)
      return true
    } catch (error) {
      endSessionTask(sessionId, operationId)
      throw error
    }
  }

  return {
    cancelRun,
    retryRun,
    sendAgentMessage,
    sendAgentSelectionMessage,
    startGeneration,
  }
}
