import React, { useState, useRef, useEffect } from 'react'
import './StartPage.css'

function StartPage({ currentSession, onGenerate, isGenerating }) {
  const [writingMode, setWritingMode] = useState('quick')
  const [templateType, setTemplateType] = useState('')
  const [quickRequirements, setQuickRequirements] = useState('')
  const [referenceDocuments, setReferenceDocuments] = useState([])
  const [referenceDocument, setReferenceDocument] = useState(null)
  const [referenceWriteType, setReferenceWriteType] = useState('general')
  const [referenceRequirements, setReferenceRequirements] = useState('')
  const [useRag, setUseRag] = useState(false)
  const fileInputRef = useRef(null)
  const templateFileInputRef = useRef(null)

  // 模板管理
  const [templates, setTemplates] = useState([])
  const [showTemplateManager, setShowTemplateManager] = useState(false)
  const [isUploadingTemplate, setIsUploadingTemplate] = useState(false)

  // 加载模板列表
  useEffect(() => {
    const loadTemplates = async () => {
      try {
        const res = await fetch('/api/templates/list')
        const json = await res.json()
        if (json.code === 200 && json.data) setTemplates(json.data)
      } catch (e) { console.error('加载模板失败:', e) }
    }
    loadTemplates()
  }, [])

  const handleFileChange = async (e) => {
    const file = e.target.files[0]
    if (!file) return

    setReferenceDocument(file)
    setReferenceDocuments(prev => [
      ...prev,
      { filename: file.name, type: 'upload', file }
    ])

    e.target.value = ''
  }

  const handleRemoveReference = (index) => {
    setReferenceDocuments(prev => prev.filter((_, i) => i !== index))
    if (index === 0 && referenceDocuments.length <= 1) {
      setReferenceDocument(null)
    }
  }

  const handleSubmit = () => {
    if (!currentSession) return

    onGenerate({
      writingMode,
      templateType,
      quickRequirements,
      referenceDocuments,
      referenceWriteType,
      referenceRequirements,
      useRag,
    })
  }

  // 上传模板
  const handleUploadTemplate = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setIsUploadingTemplate(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('name', file.name.replace('.docx', ''))
      const res = await fetch('/api/templates/upload', { method: 'POST', body: formData })
      const json = await res.json()
      if (json.code === 200) {
        // 重新加载模板列表
        const listRes = await fetch('/api/templates/list')
        const listJson = await listRes.json()
        if (listJson.code === 200 && listJson.data) setTemplates(listJson.data)
      }
    } catch (e) { console.error('上传模板失败:', e) }
    setIsUploadingTemplate(false)
    e.target.value = ''
  }

  // 设置默认模板
  const handleSetDefault = async (templateId) => {
    try {
      const res = await fetch(`/api/templates/${templateId}/set-default`, { method: 'POST' })
      const json = await res.json()
      if (json.code === 200) {
        const listRes = await fetch('/api/templates/list')
        const listJson = await listRes.json()
        if (listJson.code === 200 && listJson.data) setTemplates(listJson.data)
      }
    } catch (e) { console.error('设置默认模板失败:', e) }
  }

  // 删除模板
  const handleDeleteTemplate = async (templateId) => {
    if (!confirm('确定删除此模板？')) return
    try {
      const res = await fetch(`/api/templates/delete/${templateId}`, { method: 'DELETE' })
      const json = await res.json()
      if (json.code === 200) {
        setTemplates(prev => prev.filter(t => t.template_id !== templateId))
      }
    } catch (e) { console.error('删除模板失败:', e) }
  }

  const canGenerate = () => {
    if (!currentSession) return false
    if (writingMode === 'quick') {
      return quickRequirements.trim().length > 0
    }
    if (writingMode === 'reference') {
      return referenceDocuments.filter(d => d.type === 'upload').length > 0
    }
    return false
  }

  return (
    <div className="start-page">
      <div className="start-page-header">
        <h1>AI 写作助手</h1>
        <p className="start-page-subtitle">选择写作模式，输入要求，开始生成公文</p>
      </div>

      <div className="start-page-body">
        {/* 写作模式选择 */}
        <section className="start-section">
          <h2 className="section-title">写作模式</h2>
          <div className="mode-cards">
            <div
              className={`mode-card ${writingMode === 'quick' ? 'active' : ''}`}
              onClick={() => setWritingMode('quick')}
            >
              <div className="mode-card-icon">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                </svg>
              </div>
              <div className="mode-card-content">
                <h3>快速写作</h3>
                <p>输入写作要求，选择文体，AI 快速生成公文</p>
              </div>
            </div>
            <div
              className={`mode-card ${writingMode === 'reference' ? 'active' : ''}`}
              onClick={() => setWritingMode('reference')}
            >
              <div className="mode-card-icon">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                </svg>
              </div>
              <div className="mode-card-content">
                <h3>参考写作</h3>
                <p>上传参考文档，基于内容生成回函、仿写或相关公文</p>
              </div>
            </div>
          </div>
        </section>

        {/* 快速写作模式 */}
        {writingMode === 'quick' && (
          <>
            <section className="start-section">
              <h2 className="section-title">文体选择</h2>
              <div className="template-options-grid">
                {[
                  { value: '', label: '通用公文', desc: '适用于一般性公文写作，格式灵活通用' },
                  { value: 'notice', label: '通知', desc: '适用于发布规章制度、传达事项' },
                  { value: 'regulation', label: '规章制度', desc: '适用于制定管理办法、实施细则' },
                  { value: 'speech', label: '讲话稿', desc: '适用于会议讲话、致辞' },
                ].map(t => (
                  <div
                    key={t.value}
                    className={`template-card ${templateType === t.value ? 'active' : ''}`}
                    onClick={() => setTemplateType(t.value)}
                  >
                    <div className="template-card-label">{t.label}</div>
                    <div className="template-card-desc">{t.desc}</div>
                  </div>
                ))}
              </div>
            </section>

            <section className="start-section">
              <h2 className="section-title">写作要求</h2>
              <textarea
                value={quickRequirements}
                onChange={(e) => setQuickRequirements(e.target.value)}
                className="start-textarea"
                placeholder="请输入写作要求或大纲..."
                rows={5}
                disabled={isGenerating}
              />
            </section>
          </>
        )}

        {/* 参考写作模式 */}
        {writingMode === 'reference' && (
          <>
            <section className="start-section">
              <h2 className="section-title">参考文档</h2>
              <div
                className="upload-zone"
                onClick={() => fileInputRef.current?.click()}
              >
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
                <p className="upload-zone-text">点击上传参考文档</p>
                <p className="upload-zone-hint">支持 .docx、.md、.txt、.pdf 格式</p>
              </div>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                accept=".docx,.md,.txt,.pdf"
                style={{ display: 'none' }}
                disabled={isGenerating}
              />
              {referenceDocuments.filter(d => d.type === 'upload').length > 0 && (
                <div className="uploaded-files">
                  {referenceDocuments.filter(d => d.type === 'upload').map((doc, index) => (
                    <div key={index} className="uploaded-file-chip">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <polyline points="14 2 14 8 20 8" />
                      </svg>
                      <span>{doc.filename}</span>
                      <button onClick={() => handleRemoveReference(index)} className="file-chip-remove">×</button>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="start-section">
              <h2 className="section-title">生成类型</h2>
              <div className="template-options-grid three-col">
                {[
                  { value: 'reply', label: '生成回函', desc: '根据文档内容生成正式回函' },
                  { value: 'imitate', label: '仿写公文', desc: '学习文档风格和结构，写新主题公文' },
                  { value: 'general', label: '基于内容生成', desc: '基于文档内容生成相关公文' },
                ].map(t => (
                  <div
                    key={t.value}
                    className={`template-card ${referenceWriteType === t.value ? 'active green' : ''}`}
                    onClick={() => setReferenceWriteType(t.value)}
                  >
                    <div className="template-card-label">{t.label}</div>
                    <div className="template-card-desc">{t.desc}</div>
                  </div>
                ))}
              </div>
            </section>

            <section className="start-section">
              <h2 className="section-title">补充要求（可选）</h2>
              <textarea
                value={referenceRequirements}
                onChange={(e) => setReferenceRequirements(e.target.value)}
                className="start-textarea"
                placeholder="输入补充要求，如主题、风格要求等..."
                rows={3}
                disabled={isGenerating}
              />
            </section>
          </>
        )}

        {/* 模板管理入口 */}
        <div className="start-section template-manager-section">
          <div className="template-manager-header">
            <h2 className="section-title">导出模板</h2>
            <button className="template-mgr-btn" onClick={() => setShowTemplateManager(!showTemplateManager)}>
              {showTemplateManager ? '收起' : '管理模板'}
            </button>
          </div>
          {showTemplateManager && (
            <div className="template-manager-panel">
              <div className="template-upload-area">
                <button
                  className="template-upload-btn"
                  onClick={() => templateFileInputRef.current?.click()}
                  disabled={isUploadingTemplate}
                >
                  {isUploadingTemplate ? '上传中...' : '上传 .docx 模板'}
                </button>
                <input
                  type="file"
                  ref={templateFileInputRef}
                  onChange={handleUploadTemplate}
                  accept=".docx"
                  style={{ display: 'none' }}
                />
              </div>
              {templates.length > 0 ? (
                <div className="template-list">
                  {templates.map(t => (
                    <div key={t.template_id} className={`template-list-item ${t.is_default ? 'default' : ''}`}>
                      <div className="template-list-info">
                        <span className="template-list-name">{t.name}</span>
                        {t.description && <span className="template-list-desc">{t.description}</span>}
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
                <div className="template-empty">暂无模板，上传 .docx 文件作为导出模板</div>
              )}
            </div>
          )}
        </div>

        {/* 知识库检索开关 */}
        {writingMode === 'quick' && (
          <div className="rag-toggle">
            <label className="rag-toggle-label">
              <input
                type="checkbox"
                checked={useRag}
                onChange={(e) => setUseRag(e.target.checked)}
                disabled={isGenerating}
              />
              <span className="rag-toggle-text">启用知识库检索</span>
              <span className="rag-toggle-hint">勾选后生成时参考知识库内容，响应时间可能增加</span>
            </label>
          </div>
        )}

        {/* 生成按钮 */}
        <div className="start-page-footer">
          <button
            className="start-generate-btn"
            onClick={handleSubmit}
            disabled={!canGenerate() || isGenerating}
          >
            {isGenerating ? (
              <>
                <span className="btn-spinner"></span>
                生成中...
              </>
            ) : (
              '开始生成'
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

export default StartPage