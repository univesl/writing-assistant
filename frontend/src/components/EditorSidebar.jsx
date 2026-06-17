import React, { useState, useEffect, useRef, useCallback } from 'react'
import './EditorSidebar.css'
import { writeApi } from '../api/writeApi'

function EditorSidebar({ currentSession, currentOutput, onArticleUpdate, onEditorContentChange }) {
  const [editorContent, setEditorContent] = useState('')
  const [isEditing, setIsEditing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [isChecking, setIsChecking] = useState(false)
  const [guardResult, setGuardResult] = useState(null)
  const [showGuardResult, setShowGuardResult] = useState(false)
  const [tableOfContents, setTableOfContents] = useState([])
  const [tocWidth, setTocWidth] = useState(250)
  const contentRef = useRef(null)
  const resizeRef = useRef(null)
  const isResizingRef = useRef(false)
  const [templates, setTemplates] = useState([])
  const [selectedTemplate, setSelectedTemplate] = useState('')
  const [showTemplateMenu, setShowTemplateMenu] = useState(false)

  // AI 修改对话框状态
  const [showAIDialog, setShowAIDialog] = useState(false)
  const [aiDialogPosition, setAIDialogPosition] = useState({ x: 0, y: 0 })
  const [selectedText, setSelectedText] = useState('')
  const [aiEditRequest, setAiEditRequest] = useState('')
  const [isAiEditing, setIsAiEditing] = useState(false)
  const selectionTimeoutRef = useRef(null)
  const previewRef = useRef(null)
  const aiDialogRef = useRef(null)

  // 辅助函数：标准化文本，去除Markdown标记以便匹配
  const normalizeTextForMatching = (text) => {
    return text
      .replace(/\*\*(.+?)\*\*/g, '$1')  // 去除粗体
      .replace(/\*(.+?)\*/g, '$1')      // 去除斜体
      .replace(/`([^`]+)`/g, '$1')       // 去除行内代码
      .replace(/~~(.+?)~~/g, '$1')       // 去除删除线
      .replace(/^#+\s*/gm, '')          // 去除标题标记
      .replace(/[\[\]()]/g, '')        // 去除链接语法符号
      .replace(/\s+/g, ' ')             // 标准化空白
      .trim()
  }

  // 生成目录
  const generateTableOfContents = (content) => {
    if (!content) return []

    const lines = content.split('\n')
    const toc = []
    let idCounter = 0

    lines.forEach((line, index) => {
      // 匹配标准Markdown标题
      let headingMatch = line.match(/^(#{1,6})(?:\s+|)(.*)$/)
      let level = 1
      let text = ''

      if (headingMatch && headingMatch[2].trim()) {
        // 标准Markdown标题
        level = headingMatch[1].length
        text = headingMatch[2].trim()
      } else if (index === 0 && line.trim()) {
        // 第一行非空，视为文章标题
        text = line.trim()
        level = 1
        headingMatch = true
      } else if (/^[一二三四五六七八九十]+、/.test(line.trim()) && line.trim().length <= 30 && !line.trim().includes('。')) {
        // 中文数字标题（如"一、放假时间安排"），不超过30字且不含句号
        text = line.trim()
        level = 1
        headingMatch = true
      }

      if (headingMatch) {
        const id = `heading-${idCounter++}`

        toc.push({
          id,
          text,
          level,
          lineIndex: index,
          isMainTitle: index === 0
        })
      }
    })

    return toc
  }

  // 当currentOutput变化时，更新编辑器内容
  useEffect(() => {
    if (currentOutput) {
      // 处理**标记，移除标题中的粗体标记
      const processedContent = currentOutput
        .replace(/^\*\*(.+?)\*\*$/gm, '$1')
        .replace(/\*\*(.+?)\*\*/g, '$1')
      setEditorContent(processedContent)
    } else {
      // 当currentOutput为空时，清空编辑器内容
      setEditorContent('')
    }
    // 切换会话时退出编辑模式
    setIsEditing(false)
  }, [currentOutput])

  // 当编辑器内容变化时，更新目录
  useEffect(() => {
    setTableOfContents(generateTableOfContents(editorContent))
    if (onEditorContentChange) {
      onEditorContentChange(editorContent)
    }
  }, [editorContent, onEditorContentChange])

  // 加载模板列表
  useEffect(() => {
    const loadTemplates = async () => {
      try {
        const res = await fetch('/api/templates/list')
        const json = await res.json()
        if (json.code === 200 && json.data) {
          setTemplates(json.data)
          const defaultTpl = json.data.find(t => t.is_default)
          if (defaultTpl) setSelectedTemplate(defaultTpl.filename)
        }
      } catch (e) {
        console.error('加载模板列表失败:', e)
      }
    }
    loadTemplates()
  }, [])

  // 处理内容编辑
  const handleEditorChange = (e) => {
    setEditorContent(e.target.value)
  }

  // 跳转到指定标题
  const scrollToHeading = (lineIndex) => {
    if (contentRef.current) {
      if (isEditing) {
        // 编辑模式：滚动到textarea中的指定行
        const textarea = contentRef.current.querySelector('textarea')
        if (textarea) {
          // 计算滚动位置
          const lines = editorContent.split('\n')
          let scrollTop = 0
          for (let i = 0; i < lineIndex; i++) {
            scrollTop += lines[i].length * 8 + 16 // 估算每行高度
          }
          textarea.scrollTop = scrollTop
        }
      } else {
        // 预览模式：滚动到对应的标题元素
        const headingElement = contentRef.current.querySelector(`[data-line-index="${lineIndex}"]`)
        if (headingElement) {
          headingElement.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
          })
        }
      }
    }
  }

  // 保存编辑内容
  const handleSave = async () => {
    if (currentSession && editorContent !== currentOutput) {
      setIsSaving(true)
      try {
        if (onArticleUpdate) {
          await onArticleUpdate(currentSession.id, editorContent)
        }
      } catch (error) {
        console.error('保存失败:', error)
      } finally {
        setIsSaving(false)
      }
    }
  }

  // 切换编辑模式
  const toggleEditMode = () => {
    setIsEditing(!isEditing)
  }

  // 取消编辑
  const handleCancel = () => {
    if (currentOutput) {
      const processedContent = currentOutput
        .replace(/^\*\*(.+?)\*\*$/gm, '$1')
        .replace(/\*\*(.+?)\*\*/g, '$1')
      setEditorContent(processedContent)
    } else {
      setEditorContent('')
    }
    setIsEditing(false)
  }

  // 导出文档
  const handleExport = async (exportType) => {
    if (!currentSession || !editorContent) return
    setIsExporting(true)
    try {
      // docx 导出时使用选中的模板，否则用默认
      const referenceDoc = exportType === 'docx' ? (selectedTemplate || null) : null
      const response = await writeApi.exportDocument(currentSession.id, exportType, referenceDoc)

      let blob
      let filename

      if (response instanceof Blob) {
        blob = response
      } else if (response.data instanceof Blob) {
        blob = response.data
        const disposition = response.headers?.['content-disposition']
        if (disposition) {
          const match = disposition.match(/filename\*?=(?:UTF-8'')?([^;\s]+)/i)
          if (match) {
            filename = decodeURIComponent(match[1])
          }
        }
      } else {
        throw new Error('响应格式错误')
      }

      if (!filename) {
        const ext = exportType === 'md' ? 'md' : 'docx'
        filename = `${currentSession.name || '文档'}_${new Date().toISOString().slice(0, 10)}.${ext}`
      }

      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (error) {
      console.error('导出失败:', error)
      alert('导出失败: ' + (error.message || '未知错误'))
    } finally {
      setIsExporting(false)
    }
  }

  // 内容审查
  const handleGuardCheck = async () => {
    if (!editorContent) return
    setIsChecking(true)
    setShowGuardResult(true)
    try {
      const response = await fetch('/api/content/guard', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: editorContent })
      })
      const result = await response.json()
      if (result.code === 200) {
        setGuardResult(result.data)
      } else {
        setGuardResult({
          harmful: "error",
          harmful_type_label: "审查失败",
          harmful_reason: result.msg || '审查服务异常',
          confidence_label: '-'
        })
      }
    } catch (error) {
      console.error('内容审查失败:', error)
      setGuardResult({
        harmful: "error",
        harmful_type_label: "审查失败",
        harmful_reason: error.message || '网络错误',
        confidence_label: '-'
      })
    } finally {
      setIsChecking(false)
    }
  }

  // 关闭审查结果
  const handleCloseGuardResult = () => {
    setShowGuardResult(false)
    setGuardResult(null)
  }

  // 开始调整目录大小
  const startResizing = (e) => {
    isResizingRef.current = true
    e.preventDefault()
  }

  // 调整目录大小
  const resize = (e) => {
    if (isResizingRef.current) {
      const tocSidebar = document.querySelector('.toc-sidebar')
      const rect = tocSidebar.getBoundingClientRect()
      const newWidth = e.clientX - rect.left

      // 限制最小和最大宽度
      const maxWidth = window.innerWidth * 0.5 // 最多占据一半屏幕
      if (newWidth >= 180 && newWidth <= maxWidth) {
        setTocWidth(newWidth)
      }
    }
  }

  // 结束调整大小
  const stopResizing = () => {
    isResizingRef.current = false
  }

  // 处理选中文本 —— 弹出 AI 修改对话框
  const handleTextSelection = useCallback(() => {
    if (isEditing) return // 编辑模式下不触发

    const selection = window.getSelection()
    const text = selection.toString().trim()

    if (text.length > 0) {
      const range = selection.getRangeAt(0)
      const rect = range.getBoundingClientRect()

      setSelectedText(text)
      setAiEditRequest('')
      setAIDialogPosition({
        x: rect.left + rect.width / 2,
        y: rect.top - 10
      })
      setShowAIDialog(true)
    } else {
      setShowAIDialog(false)
      setSelectedText('')
    }
  }, [isEditing])

  // 处理 AI 修改请求
  const handleAiEdit = async () => {
    if (!selectedText || !aiEditRequest.trim() || !currentSession) return

    setIsAiEditing(true)
    try {
      const articleContent = editorContent || currentOutput || ''

      const response = await fetch('/api/write/quick', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: currentSession.id,
          mode: 'edit',
          style: 'general',
          user_requirements: aiEditRequest.trim(),
          reference_content: '',
          reference_filename: '',
          rag_content: '',
          rag_references: [],
          quotes: [selectedText],
          article_content: articleContent,
          extracted_fields: {},
          model_type: 'general',
          llm_model: 'qwen'
        })
      })

      if (response.body && response.body.getReader) {
        const reader = response.body.getReader()
        const decoder = new TextDecoder('utf-8')
        let buffer = ''
        let output = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const events = buffer.split('\n\n')
          buffer = events.pop() || ''

          for (const event of events) {
            if (event.startsWith('data:')) {
              try {
                const dataStr = event.slice(5).trim()
                if (dataStr) {
                  const data = JSON.parse(dataStr)
                  if (data.content) {
                    output += data.content
                  }
                }
              } catch (e) { }
            }
          }
        }

        if (output) {
          let articleResult = output
          const articleMatch = output.match(/---ARTICLE---\n?([\s\S]*?)(?=---SUMMARY---|$)/)
          if (articleMatch) {
            articleResult = articleMatch[1].trim()
          }

          await writeApi.saveArticle(currentSession.id, articleResult)
          if (onArticleUpdate) {
            onArticleUpdate(currentSession.id, articleResult)
          }
        }
      }
    } catch (error) {
      console.error('AI 修改失败:', error)
      alert('AI 修改失败: ' + (error.message || '未知错误'))
    } finally {
      setIsAiEditing(false)
      setShowAIDialog(false)
      setSelectedText('')
      setAiEditRequest('')
      window.getSelection().removeAllRanges()
    }
  }

  // 关闭 AI 对话框
  const handleCloseAIDialog = () => {
    setShowAIDialog(false)
    setSelectedText('')
    setAiEditRequest('')
    window.getSelection().removeAllRanges()
  }

  const handleClickOutside = useCallback((e) => {
    if (showAIDialog && aiDialogRef.current && !aiDialogRef.current.contains(e.target)) {
      handleCloseAIDialog()
    }
  }, [showAIDialog])

  useEffect(() => {
    document.addEventListener('click', handleClickOutside)
    return () => {
      document.removeEventListener('click', handleClickOutside)
    }
  }, [handleClickOutside])

  useEffect(() => {
    const previewElement = previewRef.current
    if (previewElement && !isEditing) {
      let isSelecting = false

      const handleMouseDown = () => {
        isSelecting = true
        setShowAIDialog(false)
      }

      const handleMouseUp = () => {
        if (isSelecting) {
          isSelecting = false
          if (selectionTimeoutRef.current) {
            clearTimeout(selectionTimeoutRef.current)
          }
          selectionTimeoutRef.current = setTimeout(() => {
            handleTextSelection()
          }, 100)
        }
      }

      previewElement.addEventListener('mousedown', handleMouseDown)
      previewElement.addEventListener('mouseup', handleMouseUp)

      return () => {
        previewElement.removeEventListener('mousedown', handleMouseDown)
        previewElement.removeEventListener('mouseup', handleMouseUp)
        if (selectionTimeoutRef.current) {
          clearTimeout(selectionTimeoutRef.current)
        }
      }
    }
  }, [isEditing, handleTextSelection])

  // 添加和移除事件监听器
  useEffect(() => {
    document.addEventListener('mousemove', resize)
    document.addEventListener('mouseup', stopResizing)

    return () => {
      document.removeEventListener('mousemove', resize)
      document.removeEventListener('mouseup', stopResizing)
    }
  }, [])

  if (!currentSession) {
    return null
  }

  return (
    <div className="editor-sidebar">
      {/* AI 修改对话框 */}
      {showAIDialog && (
        <div
          ref={aiDialogRef}
          className="ai-edit-dialog"
          style={{
            position: 'fixed',
            left: `${aiDialogPosition.x}px`,
            top: `${aiDialogPosition.y}px`,
            transform: 'translate(-50%, -100%)',
            zIndex: 1000
          }}
        >
          <div className="ai-edit-dialog-header">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
            </svg>
            <span>AI 修改选中内容</span>
            <button className="ai-edit-close" onClick={handleCloseAIDialog}>×</button>
          </div>
          <div className="ai-edit-dialog-body">
            <div className="ai-edit-selected-text">
              <span className="ai-edit-label">选中文本：</span>
              <p className="ai-edit-text-preview">{selectedText.length > 100 ? selectedText.substring(0, 100) + '...' : selectedText}</p>
            </div>
            <textarea
              className="ai-edit-input"
              value={aiEditRequest}
              onChange={(e) => setAiEditRequest(e.target.value)}
              placeholder="输入修改要求..."
              rows={3}
              disabled={isAiEditing}
            />
          </div>
          <div className="ai-edit-dialog-footer">
            <button className="ai-edit-btn-cancel" onClick={handleCloseAIDialog}>取消</button>
            <button
              className="ai-edit-btn-confirm"
              onClick={handleAiEdit}
              disabled={isAiEditing || !aiEditRequest.trim()}
            >
              {isAiEditing ? '修改中...' : '确认修改'}
            </button>
          </div>
        </div>
      )}

      {/* 目录调整大小的手柄（在左侧） */}
      <div
        className="resize-handle left-resize"
        onMouseDown={startResizing}
        ref={resizeRef}
      />

      {/* 左侧目录区域 */}
      <div className="toc-sidebar" style={{ width: `${tocWidth}px` }}>
        <div className="toc-header">
          <h4>目录</h4>
        </div>
        {tableOfContents.length > 0 ? (
          <ul className="toc-list">
            {tableOfContents.map((item, index) => (
              <li
                key={item.id}
                className={`toc-item level-${item.level} ${item.isMainTitle ? 'toc-main-title' : ''}`}
                onClick={() => scrollToHeading(item.lineIndex)}
              >
                {item.text}
              </li>
            ))}
          </ul>
        ) : (
          <div className="empty-toc">
            暂无目录
          </div>
        )}
      </div>

      {/* 右侧编辑器区域 */}
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
            {isEditing ? (
              <>
                <button
                  className="editor-btn save-btn"
                  onClick={handleSave}
                  disabled={isSaving}
                >
                  {isSaving ? '保存中...' : '保存'}
                </button>
                <button
                  className="editor-btn cancel-btn"
                  onClick={handleCancel}
                >
                  取消
                </button>
              </>
            ) : (
              <button
                className="editor-btn edit-btn"
                onClick={toggleEditMode}
              >
                编辑
              </button>
            )}
          </div>
        </div>

        <div className="editor-content" ref={contentRef}>
          {isEditing ? (
            <textarea
              value={editorContent}
              onChange={handleEditorChange}
              className="editor-textarea"
              placeholder="在此编辑AI生成的内容..."
              rows={20}
            />
          ) : (
            <div className="editor-preview" ref={previewRef}>
              {editorContent ? (
                <div className="content-display">
                  {editorContent.split('\n').map((line, index) => {
                    const headingMatch = line.match(/^(#{1,6})(?:\s+|)(.*)$/)
                    const trimmedLine = line.trim()

                    let isHeading = false
                    let headingLevel = 1
                    let displayText = line
                    let isMainTitle = false

                    if (headingMatch && headingMatch[2].trim()) {
                      isHeading = true
                      headingLevel = headingMatch[1].length
                      displayText = headingMatch[2].trim()
                    } else if (index === 0 && trimmedLine) {
                      isHeading = true
                      headingLevel = 1
                      displayText = trimmedLine
                    } else if (/^[一二三四五六七八九十]+、/.test(trimmedLine) && trimmedLine.length <= 30 && !trimmedLine.includes('。')) {
                      // 中文数字标题（如"一、放假时间安排"），超过30字或含句号视为正文条目
                      isHeading = true
                      headingLevel = 1
                      displayText = trimmedLine
                    }

                    displayText = displayText.replace(/\*\*(.+?)\*\*/g, '$1')

                    if (isHeading && index === 0) {
                      isMainTitle = true
                    }

                    return (
                      <div key={index} className="content-line">
                        {isHeading ? (
                          <div
                            className={`heading level-${headingLevel} ${isMainTitle ? 'main-title' : ''}`}
                            data-line-index={index}
                          >
                            {displayText}
                          </div>
                        ) : (
                          line || <br />
                        )}
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className="empty-editor">
                  暂无内容，请先生成文本
                </div>
              )}
            </div>
          )}

          {showGuardResult && guardResult && (
            <div className={`guard-result-panel ${guardResult.harmful === 'false' ? 'passed' : guardResult.harmful === 'true' ? 'failed' : 'error'}`}>
              <div className="guard-result-header">
                <span className="guard-result-icon">
                  {isChecking ? '⏳' : guardResult.harmful === 'false' ? '✅' : guardResult.harmful === 'true' ? '⚠️' : '❌'}
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
            {tableOfContents.length > 0 && (
              <span>{tableOfContents.length} 标题</span>
            )}
          </div>
          <div className="export-buttons">
            {/* docx 模板选择 */}
            <div className="template-selector-wrapper">
              <button
                className="template-select-btn"
                onClick={() => setShowTemplateMenu(!showTemplateMenu)}
                title="选择导出模板"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
                <span className="template-select-label">
                  {templates.find(t => t.filename === selectedTemplate)?.name || '默认模板'}
                </span>
              </button>
              {showTemplateMenu && (
                <div className="template-dropdown">
                  {templates.map(t => (
                    <div
                      key={t.template_id}
                      className={`template-dropdown-item ${t.filename === selectedTemplate ? 'active' : ''}`}
                      onClick={() => { setSelectedTemplate(t.filename); setShowTemplateMenu(false) }}
                    >
                      <span className="template-dropdown-name">{t.name}</span>
                      {t.description && <span className="template-dropdown-desc">{t.description}</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
            <button
              className="export-btn export-md"
              onClick={() => handleExport('md')}
              disabled={!editorContent || isExporting}
            >
              {isExporting ? '导出中...' : '导出 .md'}
            </button>
            <button
              className="export-btn export-docx"
              onClick={() => handleExport('docx')}
              disabled={!editorContent || isExporting}
            >
              {isExporting ? '导出中...' : '导出 .docx'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default EditorSidebar