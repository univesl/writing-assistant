import React, { useState, useEffect } from 'react'
import { uploadApi } from '../api/uploadApi'
import './FieldExtractionModal.css'

function FieldExtractionModal({ isOpen, onClose, currentSession }) {
  const [files, setFiles] = useState([])
  const [selectedFileId, setSelectedFileId] = useState('')
  const [models, setModels] = useState([])
  const [selectedModel, setSelectedModel] = useState('qwen3-235b-h3i')
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [extractionResult, setExtractionResult] = useState(null)
  const [editableFields, setEditableFields] = useState({})
  const [isEditing, setIsEditing] = useState(false)
  const [error, setError] = useState(null)
  const [saveSuccess, setSaveSuccess] = useState(false)

  // 字段名称映射
  const fieldNameMapping = {
    '文件标题': '文件标题',
    '来文单位': '来文单位',
    '来文字号': '来文字号',
    '原文日期': '原文日期',
    '备注': '备注',
    '时间节点': '时间节点',
    '紧急程度': '紧急程度',
    '是否需明确建议牵头单位': '是否需明确建议牵头单位',
    '阅文/办文': '阅文/办文',
    '关联文件': '关联文件',
    '收文日期': '收文日期'
  }

  // 字段类型配置（用于选择合适的输入控件）
  const fieldConfig = {
    '紧急程度': { type: 'select', options: ['', '特急', '急件', '加急', '平件'] },
    '阅文/办文': { type: 'select', options: ['', '阅文', '办文'] },
    '是否需明确建议牵头单位': { type: 'select', options: ['', '是', '否'] },
    '原文日期': { type: 'date' },
    '收文日期': { type: 'date' },
    '时间节点': { type: 'textarea', placeholder: '例如：\n2024年3月15日前：完成材料报送\n5月1日前：提交总结报告' }
  }

  // 获取会话文件列表
  const loadFiles = async () => {
    if (!currentSession) return
    
    try {
      const data = await uploadApi.getSessionFiles(currentSession.id)
      if (Array.isArray(data)) {
        const parsedFiles = data.filter(file => 
          file.status === 'completed' || file.status === 'parsed'
        )
        setFiles(parsedFiles)
      }
    } catch (err) {
      console.error('加载文件列表失败:', err)
    }
  }

  // 获取可用模型列表
  const loadModels = async () => {
    try {
      const data = await uploadApi.getAvailableModels()
      if (Array.isArray(data)) {
        setModels(data)
      }
    } catch (err) {
      console.error('加载模型列表失败:', err)
    }
  }

  // 提取字段
  const handleExtract = async () => {
    if (!selectedFileId) {
      setError('请先选择一个文件')
      return
    }

    setIsLoading(true)
    setError(null)
    setExtractionResult(null)
    setEditableFields({})
    setIsEditing(false)
    setSaveSuccess(false)

    try {
      const data = await uploadApi.extractFields(selectedFileId, selectedModel)
      if (data && data.fields) {
        setExtractionResult(data)
        setEditableFields(data.fields)
      } else {
        setError('提取失败：未返回字段数据')
      }
    } catch (err) {
      setError(err.message || '提取过程中发生错误')
    } finally {
      setIsLoading(false)
    }
  }

  // 加载已保存的字段（当选择文件时）
  const loadSavedFields = async (fileId) => {
    if (!fileId) {
      setExtractionResult(null)
      setEditableFields({})
      return
    }

    try {
      const data = await uploadApi.getFileDetail(fileId)
      if (data && data.fields) {
        setExtractionResult({ file_id: fileId, fields: data.fields })
        setEditableFields(data.fields)
      } else {
        setExtractionResult(null)
        setEditableFields({})
      }
    } catch (err) {
      console.error('加载文件详情失败:', err)
      setExtractionResult(null)
      setEditableFields({})
    }
  }

  // 处理字段值变化
  const handleFieldChange = (fieldName, value) => {
    setEditableFields(prev => ({
      ...prev,
      [fieldName]: value
    }))
    setSaveSuccess(false)
  }

  // 保存字段
  const handleSave = async () => {
    if (!selectedFileId) return

    setIsSaving(true)
    setError(null)
    setSaveSuccess(false)

    try {
      const data = await uploadApi.updateFields(selectedFileId, editableFields)
      if (data) {
        setSaveSuccess(true)
        setIsEditing(false)
        // 更新提取结果显示
        setExtractionResult(prev => ({
          ...prev,
          fields: editableFields
        }))
      }
    } catch (err) {
      setError(err.message || '保存失败')
    } finally {
      setIsSaving(false)
    }
  }

  // 取消编辑
  const handleCancelEdit = () => {
    // 恢复到原始提取结果
    if (extractionResult && extractionResult.fields) {
      setEditableFields(extractionResult.fields)
    }
    setIsEditing(false)
    setSaveSuccess(false)
  }

  // 开始编辑
  const handleStartEdit = () => {
    setIsEditing(true)
    setSaveSuccess(false)
  }

  // 弹窗打开时加载数据
  useEffect(() => {
    if (isOpen) {
      loadFiles()
      loadModels()
      setExtractionResult(null)
      setEditableFields({})
      setError(null)
      setSaveSuccess(false)
      setSelectedFileId('')
      setIsEditing(false)
    }
  }, [isOpen, currentSession])

  // 选择文件时加载已保存的字段
  useEffect(() => {
    if (selectedFileId) {
      loadSavedFields(selectedFileId)
    } else {
      setExtractionResult(null)
      setEditableFields({})
    }
  }, [selectedFileId])

  // 获取选中的文件信息
  const selectedFile = files.find(f => f.file_id === parseInt(selectedFileId))

  if (!isOpen) return null

  return (
    <div className="field-extraction-modal-overlay" onClick={onClose}>
      <div className="field-extraction-modal" onClick={e => e.stopPropagation()}>
        <div className="field-extraction-modal-header">
          <h2>信息提取</h2>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        <div className="field-extraction-modal-body">
          {/* 文件选择 */}
          <div className="file-selector">
            <label>选择要提取信息的文件：</label>
            <select 
              value={selectedFileId} 
              onChange={(e) => setSelectedFileId(e.target.value)}
              disabled={isLoading || isSaving}
            >
              <option value="">-- 请选择文件 --</option>
              {files.map(file => (
                <option key={file.file_id} value={file.file_id}>
                  {file.original_filename}
                </option>
              ))}
            </select>

            {files.length === 0 && (
              <div style={{ marginTop: '10px', color: '#999', fontSize: '13px' }}>
                当前会话没有已解析的文件，请先上传文件
              </div>
            )}

            {/* 模型选择 */}
            <div className="model-selector">
              <label>选择提取模型：</label>
              <select 
                value={selectedModel} 
                onChange={(e) => setSelectedModel(e.target.value)}
                disabled={isLoading || isSaving}
              >
                {models.map(model => (
                  <option key={model.name} value={model.name}>
                    {model.display_name || model.name}
                  </option>
                ))}
              </select>
            </div>

            <button 
              className="extract-btn"
              onClick={handleExtract}
              disabled={isLoading || isSaving || !selectedFileId}
            >
              {isLoading ? '提取中...' : '开始提取'}
            </button>
          </div>

          {/* 加载状态 */}
          {isLoading && (
            <div className="loading-state">
              <div className="loading-spinner"></div>
              <p>正在提取字段信息，请稍候...</p>
            </div>
          )}

          {/* 错误状态 */}
          {error && !isLoading && (
            <div className="error-state">
              <div className="error-state-icon">⚠️</div>
              <p>{error}</p>
              <button className="retry-btn" onClick={handleExtract}>重试</button>
            </div>
          )}

          {/* 保存成功提示 */}
          {saveSuccess && (
            <div className="success-state">
              <div className="success-state-icon">✓</div>
              <p>保存成功！</p>
            </div>
          )}

          {/* 提取结果 / 字段编辑 */}
          {!isLoading && extractionResult && (
            <div className="fields-container">
              <div className="fields-header">
                <h3>{isEditing ? '编辑字段' : '提取结果'}</h3>
                {selectedFile && (
                  <span className="file-info">
                    {selectedFile.original_filename}
                  </span>
                )}
              </div>
              
              <table className="fields-table">
                <tbody>
                  {Object.entries(fieldNameMapping).map(([key, label]) => {
                    const value = editableFields[key] || ''
                    const config = fieldConfig[key] || { type: 'text' }
                    
                    return (
                      <tr key={key}>
                        <td className="field-label">{label}</td>
                        <td className={`field-value ${!value ? 'empty' : ''}`}>
                          {isEditing ? (
                            // 编辑模式：显示输入控件
                            config.type === 'select' ? (
                              <select
                                value={value}
                                onChange={(e) => handleFieldChange(key, e.target.value)}
                                className="field-input field-select"
                              >
                                {config.options.map(opt => (
                                  <option key={opt} value={opt}>
                                    {opt || '-- 请选择 --'}
                                  </option>
                                ))}
                              </select>
                            ) : config.type === 'date' ? (
                              <input
                                type="text"
                                value={value}
                                onChange={(e) => handleFieldChange(key, e.target.value)}
                                placeholder="YYYY年MM月DD日 或 YYYY-MM-DD"
                                className="field-input"
                              />
                            ) : config.type === 'textarea' ? (
                              <textarea
                                value={value}
                                onChange={(e) => handleFieldChange(key, e.target.value)}
                                placeholder={config.placeholder || `请输入${label}`}
                                className="field-input field-textarea"
                                rows={4}
                              />
                            ) : (
                              <input
                                type="text"
                                value={value}
                                onChange={(e) => handleFieldChange(key, e.target.value)}
                                placeholder={`请输入${label}`}
                                className="field-input"
                              />
                            )
                          ) : (
                            // 查看模式：显示文本
                            value || '(未提取到)'
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>

              {/* 操作按钮 */}
              <div className="fields-actions">
                {isEditing ? (
                  <>
                    <button 
                      className="save-btn"
                      onClick={handleSave}
                      disabled={isSaving}
                    >
                      {isSaving ? '保存中...' : '保存'}
                    </button>
                    <button 
                      className="cancel-btn"
                      onClick={handleCancelEdit}
                      disabled={isSaving}
                    >
                      取消
                    </button>
                  </>
                ) : (
                  <>
                    <button 
                      className="edit-btn"
                      onClick={handleStartEdit}
                    >
                      编辑字段
                    </button>
                  </>
                )}
              </div>
            </div>
          )}

          {/* 空状态 */}
          {!isLoading && !extractionResult && (
            <div className="empty-state">
              <div className="empty-state-icon">📄</div>
              <p>选择文件并点击"开始提取"按钮获取字段信息</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default FieldExtractionModal
