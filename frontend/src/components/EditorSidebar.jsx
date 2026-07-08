import { useCallback, useEffect, useRef, useState } from 'react'
import './EditorSidebar.css'
import { writeApi } from '../api/writeApi'
import { streamQuickWrite } from '../services/writeStream'
import AiEditDialog from './editor/AiEditDialog'
import EditorToc from './editor/EditorToc'
import MarkdownArticleEditor from './editor/MarkdownArticleEditor'
import TemplateExportControls from './editor/TemplateExportControls'
import { cleanHeadingText, normalizeMarkdownStructure } from '../utils/markdownEditor'

const AI_DIALOG_WIDTH = 380
const AI_DIALOG_FALLBACK_HEIGHT = 220
const AI_DIALOG_MARGIN = 16

function EditorSidebar({
  currentSession,
  currentOutput,
  onArticleUpdate,
  onEditorContentChange,
  chatHistory = [],
  onChatHistoryUpdate,
}) {
  const [editorContent, setEditorContent] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [isChecking, setIsChecking] = useState(false)
  const [guardResult, setGuardResult] = useState(null)
  const [showGuardResult, setShowGuardResult] = useState(false)
  const [tableOfContents, setTableOfContents] = useState([])

  const [showAIDialog, setShowAIDialog] = useState(false)
  const [aiDialogPosition, setAIDialogPosition] = useState({ x: 0, y: 0 })
  const [selectedText, setSelectedText] = useState('')
  const [aiEditRequest, setAiEditRequest] = useState('')
  const [isAiEditing, setIsAiEditing] = useState(false)
  const [aiEditError, setAiEditError] = useState('')
  const [aiEditNotice, setAiEditNotice] = useState('')
  const [editorResetKey, setEditorResetKey] = useState(0)

  const contentRef = useRef(null)
  const aiDialogRef = useRef(null)
  const mdxEditorRef = useRef(null)
  const currentSessionIdRef = useRef(currentSession?.id || null)
  const editorResetTimerRef = useRef(null)
  const aiEditNoticeTimerRef = useRef(null)

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

  const updateEditorMarkdown = useCallback((nextContent) => {
    const normalizedContent = normalizeMarkdownStructure(nextContent)
    setEditorContent(normalizedContent)
    mdxEditorRef.current?.setMarkdown?.(normalizedContent)
    resetEditorHistory()
  }, [resetEditorHistory])

  useEffect(() => {
    return () => {
      if (editorResetTimerRef.current) {
        window.clearTimeout(editorResetTimerRef.current)
      }
      if (aiEditNoticeTimerRef.current) {
        window.clearTimeout(aiEditNoticeTimerRef.current)
      }
    }
  }, [])

  useEffect(() => {
    currentSessionIdRef.current = currentSession?.id || null
  }, [currentSession?.id])

  useEffect(() => {
    const nextContent = normalizeMarkdownStructure(currentOutput || '')
    setEditorContent(nextContent)
    mdxEditorRef.current?.setMarkdown?.(nextContent)
    resetEditorHistory(400)
    setShowAIDialog(false)
    setSelectedText('')
    setAiEditRequest('')
    setAiEditError('')
  }, [currentOutput, currentSession?.id, resetEditorHistory])

  useEffect(() => {
    setTableOfContents(generateTableOfContents(editorContent))
    onEditorContentChange?.(editorContent)
  }, [editorContent, generateTableOfContents, onEditorContentChange])

  const handleSave = async () => {
    if (!currentSession) return

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

  const handleGuardCheck = async () => {
    const markdown = getCurrentMarkdown()
    if (!markdown) return

    setIsChecking(true)
    setShowGuardResult(true)
    try {
      const response = await fetch('/api/content/guard', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: markdown }),
      })
      const result = await response.json()
      setGuardResult(result.code === 200 ? result.data : {
        harmful: 'error',
        harmful_type_label: '审查失败',
        harmful_reason: result.msg || '审查服务异常',
        confidence_label: '-',
      })
    } catch (error) {
      console.error('内容审查失败:', error)
      setGuardResult({
        harmful: 'error',
        harmful_type_label: '审查失败',
        harmful_reason: error.message || '网络错误',
        confidence_label: '-',
      })
    } finally {
      setIsChecking(false)
    }
  }

  const handleCloseGuardResult = () => {
    setShowGuardResult(false)
    setGuardResult(null)
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

  const readSelectedEditorText = useCallback(() => {
    const editableElement = contentRef.current?.querySelector('.wysiwyg-markdown-content')
    if (!editableElement) return ''

    const selection = window.getSelection()
    const text = selection?.toString().trim() || ''
    if (text && selection?.rangeCount) {
      const anchorNode = selection.anchorNode
      const focusNode = selection.focusNode
      if (editableElement.contains(anchorNode) && editableElement.contains(focusNode)) {
        return text
      }
    }

    return mdxEditorRef.current?.getSelectionMarkdown?.()?.trim() || ''
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

  const openAiEditDialogFromToolbar = useCallback(() => {
    const text = readSelectedEditorText()
    if (!text) {
      setShowAIDialog(false)
      setAiEditError('')
      showAiEditNotice('请先在正文中选择需要修改的内容')
      return
    }

    setSelectedText(text)
    setAiEditRequest('')
    setAiEditError('')
    setAiEditNotice('')
    setAIDialogPosition(getDefaultAiDialogPosition())
    setShowAIDialog(true)
  }, [getDefaultAiDialogPosition, readSelectedEditorText, showAiEditNotice])

  const handleCloseAIDialog = useCallback(() => {
    setShowAIDialog(false)
    setSelectedText('')
    setAiEditRequest('')
    setAiEditError('')
    window.getSelection()?.removeAllRanges()
  }, [])

  const handleClickOutside = useCallback((e) => {
    if (!showAIDialog) return
    if (aiDialogRef.current?.contains(e.target)) return
    if (contentRef.current?.contains(e.target)) return
    handleCloseAIDialog()
  }, [handleCloseAIDialog, showAIDialog])

  useEffect(() => {
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [handleClickOutside])

  const saveChatMessage = async (sessionId, message, role) => {
    await writeApi.saveContent(sessionId, message, 'quick', 'chat', role)
  }

  const handleAiEdit = async () => {
    if (!currentSession) return
    if (!selectedText.trim()) {
      setAiEditError('请先在正文中选择需要修改的内容')
      return
    }
    if (!aiEditRequest.trim()) return

    const editSessionId = currentSession.id
    const articleContent = getCurrentMarkdown()
    const instruction = aiEditRequest.trim()
    const userMessage = `选中内容：\n「${selectedText}」\n\n修改意见：\n${instruction}`
    const nextChatHistory = [...(Array.isArray(chatHistory) ? chatHistory : []), {
      role: 'user',
      content: userMessage,
    }]

    setIsAiEditing(true)
    setAiEditError('')

    try {
      onChatHistoryUpdate?.(editSessionId, nextChatHistory)
      saveChatMessage(editSessionId, userMessage, 'user').catch(() => {})

      const { articleContent: articleResult, summaryContent } = await streamQuickWrite({
        payload: {
          session_id: editSessionId,
          mode: 'edit',
          style: 'general',
          user_requirements: instruction,
          reference_content: '',
          reference_filename: '',
          rag_content: '',
          rag_references: [],
          quotes: [selectedText],
          article_content: articleContent,
          extracted_fields: {},
          model_type: 'general',
          llm_model: 'qwen',
        },
        fallbackSummary: '已完成修改',
        requireArticleMarker: true,
      })

      await writeApi.saveArticle(editSessionId, articleResult)

      if (editSessionId === currentSessionIdRef.current) {
        updateEditorMarkdown(articleResult)
        onArticleUpdate?.(editSessionId, articleResult, { persist: false })
        const updatedChatHistory = [...nextChatHistory, {
          role: 'assistant',
          content: summaryContent,
        }]
        onChatHistoryUpdate?.(editSessionId, updatedChatHistory)
      }

      await saveChatMessage(editSessionId, summaryContent, 'assistant')
      handleCloseAIDialog()
      window.getSelection()?.removeAllRanges()
    } catch (error) {
      console.error('AI 局部修改失败:', error)
      setAiEditError(error.message || 'AI 修改失败，请重试')
    } finally {
      setIsAiEditing(false)
    }
  }

  const handleMarkdownChange = (markdown, initialMarkdownNormalize) => {
    if (initialMarkdownNormalize) return

    const normalizedMarkdown = normalizeMarkdownStructure(markdown || '')
    setEditorContent(normalizedMarkdown)

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
    <div className="editor-sidebar">
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
          <h3>文本编辑器</h3>
          <div className="editor-actions">
            <button
              className="editor-btn guard-btn"
              onClick={handleGuardCheck}
              disabled={!editorContent || isChecking}
            >
              {isChecking ? '审查中...' : '内容审查'}
            </button>
            <button
              className="editor-btn save-btn"
              onClick={handleSave}
              disabled={isSaving}
            >
              {isSaving ? '保存中...' : '保存'}
            </button>
          </div>
        </div>

        <div
          className="editor-content"
          ref={contentRef}
        >
          {aiEditNotice && (
            <div className="ai-edit-notice">{aiEditNotice}</div>
          )}

          <MarkdownArticleEditor
            key={editorResetKey}
            editorRef={mdxEditorRef}
            markdown={editorContent}
            onChange={handleMarkdownChange}
            onAiEditRequest={openAiEditDialogFromToolbar}
          />

          {showGuardResult && guardResult && (
            <div className={`guard-result-panel ${guardResult.harmful === 'false' ? 'passed' : guardResult.harmful === 'true' ? 'failed' : 'error'}`}>
              <div className="guard-result-header">
                <span className="guard-result-icon">
                  {isChecking ? '...' : guardResult.harmful === 'false' ? '✓' : guardResult.harmful === 'true' ? '!' : '×'}
                </span>
                <span className="guard-result-title">
                  {isChecking ? '正在审查...' : guardResult.harmful === 'false' ? '内容审查通过' : guardResult.harmful === 'true' ? '内容审查未通过' : '审查失败'}
                </span>
                <button className="guard-result-close" onClick={handleCloseGuardResult}>×</button>
              </div>
              {!isChecking && (
                <div className="guard-result-body">
                  {guardResult.harmful === 'false' && (
                    <div className="guard-result-passed">
                      <p>未发现违规内容</p>
                      <span className="guard-confidence">置信度：{guardResult.confidence_label}</span>
                    </div>
                  )}
                  {guardResult.harmful === 'true' && (
                    <div className="guard-result-details">
                      {guardResult.harmful_type_label && guardResult.harmful_type_label !== '无' && (
                        <div className="guard-detail-item">
                          <span className="guard-detail-label">违规类型：</span>
                          <span className="guard-detail-value">{guardResult.harmful_type_label}</span>
                        </div>
                      )}
                      {guardResult.harmful_degree_label && guardResult.harmful_degree_label !== '无' && (
                        <div className="guard-detail-item">
                          <span className="guard-detail-label">违规程度：</span>
                          <span className="guard-detail-value">{guardResult.harmful_degree_label}</span>
                        </div>
                      )}
                      {guardResult.harmful_reason && (
                        <div className="guard-detail-item">
                          <span className="guard-detail-label">违规原因：</span>
                          <span className="guard-detail-value">{guardResult.harmful_reason}</span>
                        </div>
                      )}
                      {guardResult.harmful_words && (
                        <div className="guard-detail-item">
                          <span className="guard-detail-label">违规词汇：</span>
                          <span className="guard-detail-value harmful-words">{guardResult.harmful_words}</span>
                        </div>
                      )}
                      {guardResult.highlight_spans && guardResult.highlight_spans.length > 0 && (
                        <div className="guard-detail-item">
                          <span className="guard-detail-label">高亮片段：</span>
                          <div className="guard-highlight-spans">
                            {guardResult.highlight_spans.map((span, i) => (
                              <span key={i} className="guard-highlight-span">{span}</span>
                            ))}
                          </div>
                        </div>
                      )}
                      <span className="guard-confidence">置信度：{guardResult.confidence_label}</span>
                    </div>
                  )}
                  {guardResult.harmful === 'error' && (
                    <div className="guard-result-error">
                      <p>{guardResult.harmful_reason}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
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
