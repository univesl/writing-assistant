import { useEffect, useRef, useState } from 'react'
import { writeApi } from '../../api/writeApi'

function TemplateExportControls({
  currentSession,
  editorContent,
  currentOutput,
  getCurrentMarkdown,
  onArticleUpdate,
  onContentSaved,
}) {
  const [templates, setTemplates] = useState([])
  const [selectedTemplate, setSelectedTemplate] = useState('')
  const [showTemplateMenu, setShowTemplateMenu] = useState(false)
  const [showTemplateManager, setShowTemplateManager] = useState(false)
  const [isUploadingTemplate, setIsUploadingTemplate] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const templateFileInputRef = useRef(null)

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

  const reloadTemplates = async () => {
    try {
      const res = await fetch('/api/templates/list')
      const json = await res.json()
      if (json.code === 200 && json.data) setTemplates(json.data)
    } catch (e) {
      console.error('加载模板失败:', e)
    }
  }

  const handleUploadTemplate = async (e) => {
    const file = e.target.files[0]
    if (!file) return

    setIsUploadingTemplate(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('name', file.name.replace('.docx', ''))
      await fetch('/api/templates/upload', { method: 'POST', body: formData })
      await reloadTemplates()
    } catch (e) {
      console.error('上传模板失败:', e)
    } finally {
      setIsUploadingTemplate(false)
      e.target.value = ''
    }
  }

  const handleSetDefault = async (templateId) => {
    try {
      await fetch(`/api/templates/${templateId}/set-default`, { method: 'POST' })
      await reloadTemplates()
    } catch (e) {
      console.error('设置默认模板失败:', e)
    }
  }

  const handleDeleteTemplate = async (templateId) => {
    if (!confirm('确定删除此模板？')) return
    try {
      await fetch(`/api/templates/delete/${templateId}`, { method: 'DELETE' })
      setTemplates(prev => prev.filter(t => t.template_id !== templateId))
    } catch (e) {
      console.error('删除模板失败:', e)
    }
  }

  const handleExport = async (exportType) => {
    if (!currentSession || !editorContent) return

    setIsExporting(true)
    try {
      const markdown = getCurrentMarkdown()
      if (markdown !== currentOutput) {
        await writeApi.saveArticle(currentSession.id, markdown)
        onContentSaved?.(markdown)
        onArticleUpdate?.(currentSession.id, markdown, { persist: false })
      }

      const referenceDoc = exportType === 'docx' ? (selectedTemplate || null) : null
      const response = await writeApi.exportDocument(currentSession.id, exportType, referenceDoc)

      let blob
      let filename
      if (response instanceof Blob) {
        blob = response
      } else if (response.data instanceof Blob) {
        blob = response.data
        const disposition = response.headers?.['content-disposition']
        const match = disposition?.match(/filename\*?=(?:UTF-8'')?([^;\s]+)/i)
        if (match) filename = decodeURIComponent(match[1])
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

  return (
    <>
      {showTemplateManager && (
        <div className="template-manager-overlay" onClick={() => setShowTemplateManager(false)}>
          <div className="template-manager-dialog" onClick={e => e.stopPropagation()}>
            <div className="template-manager-dialog-header">
              <h4>模板管理</h4>
              <button className="template-mgr-close" onClick={() => setShowTemplateManager(false)}>×</button>
            </div>
            <div className="template-manager-dialog-body">
              <button
                className="template-upload-btn"
                onClick={() => templateFileInputRef.current?.click()}
                disabled={isUploadingTemplate}
              >
                {isUploadingTemplate ? '上传中...' : '上传 .docx 模板'}
              </button>
              <input type="file" ref={templateFileInputRef} onChange={handleUploadTemplate} accept=".docx" style={{ display: 'none' }} />
              {templates.length > 0 ? (
                <div className="template-list">
                  {templates.map(t => (
                    <div key={t.template_id} className={`template-list-item ${t.is_default ? 'default' : ''}`}>
                      <div className="template-list-info">
                        <span className="template-list-name">{t.name}</span>
                        {t.is_default && <span className="template-list-badge">默认</span>}
                      </div>
                      <div className="template-list-actions">
                        {!t.is_default && (
                          <button className="template-action-btn set-default" onClick={() => handleSetDefault(t.template_id)}>设为默认</button>
                        )}
                        <button className="template-action-btn delete" onClick={() => handleDeleteTemplate(t.template_id)}>删除</button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="template-empty">暂无模板</div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="export-buttons">
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
                  {t.is_default && <span className="template-dropdown-badge">默认</span>}
                </div>
              ))}
              <div className="template-dropdown-divider"></div>
              <div
                className="template-dropdown-item manage"
                onClick={() => { setShowTemplateMenu(false); setShowTemplateManager(true) }}
              >
                <span className="template-dropdown-name">管理模板...</span>
              </div>
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
    </>
  )
}

export default TemplateExportControls
