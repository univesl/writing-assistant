import { useCallback, useEffect, useRef, useState } from 'react'
import '../../styles/editor.css'
import { writeApi } from '../../api/writeApi'
import { streamSelectionEdit } from '../../services/writeStream'
import AiEditDialog from './AiEditDialog'
import EditorToc from './EditorToc'
import MarkdownArticleEditor from './MarkdownArticleEditor'
import TemplateExportControls from './TemplateExportControls'
import { cleanHeadingText, normalizeMarkdownStructure } from '../../utils/markdownEditor'
import {
  replaceUniqueTextFragment,
  sameArticleSnapshot,
} from '../../utils/selectionReplacement'
import { normalizeOfficialArticleFormat } from '../../utils/generatedOutput'

const AI_DIALOG_WIDTH = 380
const AI_DIALOG_FALLBACK_HEIGHT = 220
const AI_DIALOG_MARGIN = 16
const EMPTY_SELECTION_CONTEXT = Object.freeze({
  document_title: '',
  section_heading: '',
  context_before: '',
  context_after: '',
})

function EditorSidebar({
  currentSession,
  currentOutput,
  onArticleUpdate,
  onEditorContentChange,
  chatHistory = [],
  onChatHistoryUpdate,
  isBusy = false,
  onTaskStart,
  onTaskFinish,
  isSessionActive,
  onAgentSelectionMessage,
  style,
}) {
  const [editorContent, setEditorContent] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [tableOfContents, setTableOfContents] = useState([])

  const [showAIDialog, setShowAIDialog] = useState(false)
  const [aiDialogPosition, setAIDialogPosition] = useState({ x: 0, y: 0 })
  const [selectedMarkdown, setSelectedMarkdown] = useState('')
  const [selectionContext, setSelectionContext] = useState(EMPTY_SELECTION_CONTEXT)
  const [aiEditRequest, setAiEditRequest] = useState('')
  const [isAiEditing, setIsAiEditing] = useState(false)
  const [aiEditError, setAiEditError] = useState('')
  const [aiEditNotice, setAiEditNotice] = useState('')
  const [editorResetKey, setEditorResetKey] = useState(0)

  const contentRef = useRef(null)
  const aiDialogRef = useRef(null)
  const mdxEditorRef = useRef(null)
  const selectionBridgeRef = useRef(null)
  const currentSessionIdRef = useRef(currentSession?.id || null)
  const editorResetTimerRef = useRef(null)
  const aiEditNoticeTimerRef = useRef(null)
  const pendingEditorChangeRef = useRef(null)
  const skipExternalSyncRef = useRef(null)

  const generateTableOfContents = useCallback((content) => {
    if (!content) return []

    const toc = []
    let headingIndex = 0
    content.split('\n').forEach((line, lineIndex) => {
      const headingMatch = line.match(/^(#{1,6})\s+(.+)$/)
      if (!headingMatch) return

      toc.push({
        id: `heading-${headingIndex}`,
        headingIndex,
        text: cleanHeadingText(headingMatch[2]),
        level: headingMatch[1].length,
        lineIndex,
        isMainTitle: headingMatch[1].length === 1 && toc.length === 0,
      })
      headingIndex += 1
    })
    return toc
  }, [])

  const getCurrentMarkdown = useCallback(() => {
    return normalizeMarkdownStructure(mdxEditorRef.current?.getMarkdown?.() ?? editorContent ?? '')
  }, [editorContent])

  const resetEditorHistory = useCallback((delay = 0) => {
    if (editorResetTimerRef.current) {
      window.clearTimeout(editorResetTimerRef.current)
    }

    const reset = () => {
      setEditorResetKey(key => key + 1)
      editorResetTimerRef.current = null
    }

    if (delay > 0) {
      editorResetTimerRef.current = window.setTimeout(reset, delay)
    } else {
      reset()
    }
  }, [])

  const waitForNextEditorChange = useCallback(() => {
    return new Promise((resolve, reject) => {
      if (pendingEditorChangeRef.current) {
        window.clearTimeout(pendingEditorChangeRef.current.timeoutId)
      }

      const timeoutId = window.setTimeout(() => {
        pendingEditorChangeRef.current = null
        reject(new Error('编辑器未能应用选区修改，请重新选择后再试'))
      }, 2000)

      pendingEditorChangeRef.current = { resolve, reject, timeoutId }
    })
  }, [])

  const discardPendingEditorChange = useCallback(() => {
    if (!pendingEditorChangeRef.current) return
    window.clearTimeout(pendingEditorChangeRef.current.timeoutId)
    pendingEditorChangeRef.current = null
  }, [])

  useEffect(() => {
    return () => {
      if (editorResetTimerRef.current) {
        window.clearTimeout(editorResetTimerRef.current)
      }
      if (aiEditNoticeTimerRef.current) {
        window.clearTimeout(aiEditNoticeTimerRef.current)
      }
      discardPendingEditorChange()
    }
  }, [discardPendingEditorChange])

  useEffect(() => {
    currentSessionIdRef.current = currentSession?.id || null
  }, [currentSession?.id])

  useEffect(() => {
    const nextContent = normalizeMarkdownStructure(currentOutput || '')
    const skippedSync = skipExternalSyncRef.current
    if (
      skippedSync &&
      skippedSync.sessionId === currentSession?.id &&
      skippedSync.content === nextContent
    ) {
      skipExternalSyncRef.current = null
      return
    }

    skipExternalSyncRef.current = null
    selectionBridgeRef.current?.clear?.()
    discardPendingEditorChange()
    setEditorContent(nextContent)
    mdxEditorRef.current?.setMarkdown?.(nextContent)
    resetEditorHistory(400)
    setShowAIDialog(false)
    setSelectedMarkdown('')
    setSelectionContext(EMPTY_SELECTION_CONTEXT)
    setAiEditRequest('')
    setAiEditError('')
  }, [currentOutput, currentSession?.id, discardPendingEditorChange, resetEditorHistory])

  useEffect(() => {
    setTableOfContents(generateTableOfContents(editorContent))
    onEditorContentChange?.(currentSession?.id, editorContent)
  }, [currentSession?.id, editorContent, generateTableOfContents, onEditorContentChange])

  const handleSave = async () => {
    if (!currentSession || isBusy) return

    const markdown = getCurrentMarkdown()
    if (markdown === currentOutput) return

    setIsSaving(true)
    try {
      await onArticleUpdate?.(currentSession.id, markdown)
      setEditorContent(markdown)
    } catch (error) {
      console.error('保存失败:', error)
      alert('保存失败: ' + (error.message || '未知错误'))
    } finally {
      setIsSaving(false)
    }
  }

  const showAiEditNotice = useCallback((message) => {
    setAiEditNotice(message)
    if (aiEditNoticeTimerRef.current) {
      window.clearTimeout(aiEditNoticeTimerRef.current)
    }
    aiEditNoticeTimerRef.current = window.setTimeout(() => {
      setAiEditNotice('')
      aiEditNoticeTimerRef.current = null
    }, 2200)
  }, [])

  const readSelectedEditorSelection = useCallback(() => {
    const captured = selectionBridgeRef.current?.capture?.()
    if (!captured) return null
    if (captured.error) return { error: captured.error }

    const markdown = captured.selectedMarkdown || ''
    if (markdown.trim()) return { markdown, context: captured.context }

    selectionBridgeRef.current?.clear?.()
    return null
  }, [])

  const getDefaultAiDialogPosition = useCallback(() => {
    const editorRect = contentRef.current?.getBoundingClientRect()
    if (!editorRect) {
      return { x: 0, y: 0 }
    }

    const dialogHeight = aiDialogRef.current?.offsetHeight || AI_DIALOG_FALLBACK_HEIGHT
    const minX = editorRect.left + AI_DIALOG_MARGIN
    const maxX = editorRect.right - AI_DIALOG_WIDTH - AI_DIALOG_MARGIN
    const minY = editorRect.top + AI_DIALOG_MARGIN
    const maxY = editorRect.bottom - dialogHeight - AI_DIALOG_MARGIN

    return {
      x: Math.min(Math.max(editorRect.right - AI_DIALOG_WIDTH - 28, minX), Math.max(minX, maxX)),
      y: Math.min(Math.max(editorRect.top + 76, minY), Math.max(minY, maxY)),
    }
  }, [])

  const openAiEditDialogFromToolbar = useCallback((selected) => {
    // 鼠标按下按钮后，浏览器会把焦点移出正文并清空原生高亮。
    // 这里只消费 pointerdown 阶段冻结的结果，不能在 click 阶段重新猜测范围。
    if (selected?.error) {
      setShowAIDialog(false)
      setAiEditError('')
      showAiEditNotice(selected.error)
      return
    }
    if (!selected) {
      setShowAIDialog(false)
      setAiEditError('')
      showAiEditNotice('请先在正文中选择需要修改的内容')
      return
    }

    setSelectedMarkdown(selected.markdown)
    setSelectionContext(selected.context)
    setAiEditRequest('')
    setAiEditError('')
    setAiEditNotice('')
    setAIDialogPosition(getDefaultAiDialogPosition())
    setShowAIDialog(true)
  }, [getDefaultAiDialogPosition, showAiEditNotice])

  const resetAiEditDialog = useCallback(() => {
    setShowAIDialog(false)
    setSelectedMarkdown('')
    setSelectionContext(EMPTY_SELECTION_CONTEXT)
    setAiEditRequest('')
    setAiEditError('')
    selectionBridgeRef.current?.clear?.()
    window.getSelection()?.removeAllRanges()
  }, [])

  const handleCloseAIDialog = useCallback(() => {
    if (isAiEditing) return
    resetAiEditDialog()
  }, [isAiEditing, resetAiEditDialog])

  const handleClickOutside = useCallback((e) => {
    if (!showAIDialog || isAiEditing) return
    if (aiDialogRef.current?.contains(e.target)) return
    handleCloseAIDialog()
  }, [handleCloseAIDialog, isAiEditing, showAIDialog])

  useEffect(() => {
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [handleClickOutside])

  const saveChatMessage = async (sessionId, message, role) => {
    await writeApi.saveContent(sessionId, message, 'quick', 'chat', role)
  }

  const handleAiEdit = async () => {
    if (!currentSession || isBusy) return
    if (!selectedMarkdown.trim()) {
      setAiEditError('请先在正文中选择需要修改的内容')
      return
    }
    if (!aiEditRequest.trim()) return

    const editSessionId = currentSession.id
    const articleContent = getCurrentMarkdown()
    const instruction = aiEditRequest.trim()
    const userMessage = `选中内容：\n「${selectedMarkdown}」\n\n修改意见：\n${instruction}`
    const nextChatHistory = [...(Array.isArray(chatHistory) ? chatHistory : []), {
      role: 'user',
      content: userMessage,
    }]

    if (onAgentSelectionMessage) {
      setIsAiEditing(true)
      setAiEditError('')
      try {
        await onAgentSelectionMessage({
          instruction,
          selectedMarkdown,
          selectionContext,
          baseArticle: articleContent,
        })
        resetAiEditDialog()
      } catch (error) {
        setAiEditError(error.message || '无法创建选区修改任务')
      } finally {
        setIsAiEditing(false)
      }
      return
    }

    const operationId = onTaskStart
      ? onTaskStart(editSessionId, 'selection-edit', '正在根据上下文修改选区，请稍候…')
      : `local-${Date.now()}`
    if (!operationId) {
      setAiEditError('该会话已有正文任务运行，请完成后再试')
      return
    }

    setIsAiEditing(true)
    setAiEditError('')
    let selectionApplied = false

    try {
      onChatHistoryUpdate?.(editSessionId, nextChatHistory)
      saveChatMessage(editSessionId, userMessage, 'user').catch(() => {})

      const { replacementMarkdown, summaryContent } = await streamSelectionEdit({
        payload: {
          session_id: editSessionId,
          selected_markdown: selectedMarkdown,
          ...selectionContext,
          instruction,
          style: 'general',
          llm_model: 'xhang',
        },
      })

      const sessionIsActive = () => (
        isSessionActive
          ? isSessionActive(editSessionId)
          : editSessionId === currentSessionIdRef.current
      )
      const replacementIsNoop = replacementMarkdown === selectedMarkdown.trim()
      let updatedArticle = articleContent

      if (sessionIsActive() && selectionBridgeRef.current?.apply) {
        if (getCurrentMarkdown() !== articleContent) {
          throw new Error('等待期间文章内容已变化，本次修改未应用；请重新选择最新内容')
        }

        if (!replacementIsNoop) {
          const editorChange = waitForNextEditorChange()
          try {
            selectionBridgeRef.current.apply(replacementMarkdown)
          } catch (error) {
            discardPendingEditorChange()
            throw error
          }
          updatedArticle = await editorChange
          selectionApplied = true

          skipExternalSyncRef.current = {
            sessionId: editSessionId,
            content: updatedArticle,
          }
          await onArticleUpdate?.(editSessionId, updatedArticle, { persist: false })

          try {
            await writeApi.saveArticle(editSessionId, updatedArticle)
          } catch {
            throw new Error('修改已应用，但自动保存失败，请点击“保存”按钮重试')
          }
        } else {
          selectionBridgeRef.current.clear?.()
        }
      } else if (!replacementIsNoop) {
        // 任务属于已切换到后台的会话。此时原 Lexical 编辑器已经卸载，
        // 不能把结果写进当前会话，也不能凭相似度猜文章位置；重新读取原会话
        // 的最新快照，并且只允许唯一选区匹配后落盘。
        const latestArticleResponse = await writeApi.getArticle(editSessionId)
        const latestArticle = normalizeOfficialArticleFormat(
          normalizeMarkdownStructure(latestArticleResponse?.article_content || ''),
        )
        if (!sameArticleSnapshot(latestArticle, articleContent)) {
          throw new Error('等待期间原会话文章已变化，未应用后台修改；请重新选择最新内容')
        }

        const backgroundReplacement = replaceUniqueTextFragment(
          latestArticle,
          selectedMarkdown,
          replacementMarkdown,
        )
        if (!backgroundReplacement.ok) {
          throw new Error(backgroundReplacement.reason)
        }

        updatedArticle = backgroundReplacement.content
        await writeApi.saveArticle(editSessionId, updatedArticle)
        selectionApplied = true

        // 用户可能在后台请求完成前切回原会话；此时把已经落盘的结果同步到
        // 当前界面，否则由下一次会话加载兜底。
        if (sessionIsActive()) {
          await onArticleUpdate?.(editSessionId, updatedArticle, { persist: false })
        }
      } else {
        selectionBridgeRef.current?.clear?.()
      }

      if (sessionIsActive()) {
        const updatedChatHistory = [...nextChatHistory, {
          role: 'assistant',
          content: summaryContent,
        }]
        onChatHistoryUpdate?.(editSessionId, updatedChatHistory)
      }

      saveChatMessage(editSessionId, summaryContent, 'assistant').catch(() => {})
      if (sessionIsActive()) resetAiEditDialog()
    } catch (error) {
      console.error('AI 局部修改失败:', error)
      if (selectionApplied) {
        if (isSessionActive?.(editSessionId) ?? editSessionId === currentSessionIdRef.current) {
          resetAiEditDialog()
          showAiEditNotice(error.message || '修改已应用，请手动保存')
        }
      } else {
        if (isSessionActive?.(editSessionId) ?? editSessionId === currentSessionIdRef.current) {
          setAiEditError(error.message || 'AI 修改失败，请重试')
        }
      }
    } finally {
      setIsAiEditing(false)
      onTaskFinish?.(editSessionId, operationId)
    }
  }

  const handleMarkdownChange = (markdown, initialMarkdownNormalize) => {
    if (initialMarkdownNormalize) return

    const normalizedMarkdown = normalizeMarkdownStructure(markdown || '')
    setEditorContent(normalizedMarkdown)

    if (pendingEditorChangeRef.current) {
      const pendingChange = pendingEditorChangeRef.current
      window.clearTimeout(pendingChange.timeoutId)
      pendingEditorChangeRef.current = null
      pendingChange.resolve(normalizedMarkdown)
    }

    if (normalizedMarkdown !== (markdown || '')) {
      window.setTimeout(() => {
        mdxEditorRef.current?.setMarkdown?.(normalizedMarkdown)
        resetEditorHistory()
      }, 0)
    }
  }

  if (!currentSession) {
    return null
  }

  return (
    <div className="editor-sidebar" style={style}>
      {showAIDialog && (
        <AiEditDialog
          boundaryRef={contentRef}
          dialogRef={aiDialogRef}
          position={aiDialogPosition}
          onPositionChange={setAIDialogPosition}
          request={aiEditRequest}
          onRequestChange={setAiEditRequest}
          error={aiEditError}
          isSubmitting={isAiEditing}
          onSubmit={handleAiEdit}
          onCancel={handleCloseAIDialog}
        />
      )}

      <EditorToc items={tableOfContents} contentRef={contentRef} />

      <div className="editor-main">
        <div className="editor-header">
          <strong className="editor-title">正文编辑</strong>
          <div className="editor-actions">
            <button
              className="editor-btn save-btn"
              onClick={handleSave}
              disabled={isSaving || isBusy}
            >
              {isSaving ? '保存中...' : '保存'}
            </button>
          </div>
        </div>

        <div
          className="editor-content"
          ref={contentRef}
          onMouseDownCapture={isAiEditing ? (event) => {
            event.preventDefault()
            event.stopPropagation()
          } : undefined}
          onKeyDownCapture={isAiEditing ? (event) => {
            event.preventDefault()
            event.stopPropagation()
          } : undefined}
        >
          {aiEditNotice && (
            <div className="ai-edit-notice" role="alert" aria-live="assertive">
              {aiEditNotice}
            </div>
          )}

          <MarkdownArticleEditor
            key={editorResetKey}
            editorRef={mdxEditorRef}
            markdown={editorContent}
            onChange={handleMarkdownChange}
            onAiEditPrepare={readSelectedEditorSelection}
            onAiEditRequest={openAiEditDialogFromToolbar}
            selectionBridgeRef={selectionBridgeRef}
            interactionLocked={isAiEditing || isBusy}
          />

        </div>

        <div className="editor-footer">
          <div className="content-stats">
            <span>{editorContent.length} 字符</span>
            <span>{editorContent.split('\n').length} 行数</span>
            {tableOfContents.length > 0 && <span>{tableOfContents.length} 标题</span>}
          </div>

          <TemplateExportControls
            currentSession={currentSession}
            editorContent={editorContent}
            currentOutput={currentOutput}
            getCurrentMarkdown={getCurrentMarkdown}
            onArticleUpdate={onArticleUpdate}
            onContentSaved={setEditorContent}
          />
        </div>
      </div>
    </div>
  )
}

export default EditorSidebar
