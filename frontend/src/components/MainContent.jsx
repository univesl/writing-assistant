import React, { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { writeApi } from '../api/writeApi'

function MainContent({ currentSession, currentOutput, onContentUpdate }) {
  const [outputText, setOutputText] = useState(currentOutput || '')
  const [isGenerating, setIsGenerating] = useState(false)
  
  // 快速写作的模板化参数
  const [textType, setTextType] = useState('')
  const [articleTitle, setArticleTitle] = useState('')
  const [articleLength, setArticleLength] = useState('')
  const [articleStyle, setArticleStyle] = useState('')
  const [otherRequirements, setOtherRequirements] = useState('')
  
  // 参考文档相关状态
  const [referenceDocuments, setReferenceDocuments] = useState([])
  const fileInputRef = React.useRef(null)
  
  // 监听currentOutput变化，当会话切换时更新内容
  useEffect(() => {
    setOutputText(currentOutput || '')
  }, [currentOutput])

  const handleGenerate = async () => {
    if (!currentSession) return
    
    // 快速写作模式下检查必要参数
    if (!textType) return
    
    // 检查文章标题是否填写
    if (!articleTitle || articleTitle.trim() === '') {
      alert('请填写文章标题')
      return
    }
    
    console.log('用户点击生成按钮')
    console.log('当前会话ID:', currentSession.id)
    
    setIsGenerating(true)
    setOutputText('生成中...')
    
    try {
      // 构建快速写作的提示词
      let prompt = `帮我写一篇${textType}`
      if (articleTitle) prompt += `，文章标题是${articleTitle}`
      if (articleLength) prompt += `，文章篇幅${articleLength}字左右`
      if (articleStyle) prompt += `，风格${articleStyle}`
      if (otherRequirements) prompt += `，其他要求${otherRequirements}`
      
      // 如果有参考文档，添加到提示词中
      if (referenceDocuments.length > 0) {
        prompt += `\n\n参考文档内容：\n`
        referenceDocuments.forEach((doc, index) => {
          prompt += `\n--- 参考文档 ${index + 1}: ${doc.filename} ---\n`
          prompt += `${doc.content}\n`
        })
      }
      
      prompt += `。`
      
      console.log('构建的提示词:', prompt)
      
      // 直接使用fetch API测试SSE响应
      const url = 'http://127.0.0.1:8000/api/write/quick'
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          session_id: currentSession.id,
          prompt: prompt,
          model_type: 'general'
        })
      })
      
      console.log('Fetch response:', response)
      console.log('Response type:', response.type)
      console.log('Is readable:', response.body?.readable)
      
      if (response.body && response.body.getReader) {
        const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
        let output = ''
        
        try {
          while (true) {
            const { done, value } = await reader.read()
            console.log('Stream chunk:', { done, value })
            if (done) {
              console.log('Stream reading completed')
              break
            }
            
            if (value) {
              const lines = value.split('\n')
              console.log('Parsed lines:', lines)
              for (const line of lines) {
                if (line && line.startsWith('data:')) {
                  try {
                    const dataStr = line.slice(5).trim()
                    if (dataStr) {
                      const data = JSON.parse(dataStr)
                      console.log('Parsed data:', data)
                      if (data.content) {
                        output += data.content
                        setOutputText(output)
                        // 更新会话内容到全局状态
                        if (onContentUpdate) {
                          onContentUpdate(currentSession.id, output)
                        }
                        console.log('Output updated:', output)
                      }
                      if (data.finish) {
                        console.log('Generation finished signal received')
                      }
                    }
                  } catch (e) {
                    console.error('Parse error:', e)
                    console.error('Line causing error:', line)
                  }
                } else if (line) {
                  console.log('Non-data line:', line)
                }
              }
            } else {
              console.log('Received empty chunk')
            }
          }
          
          const result = { content: output }
          console.log('Final result:', result)
          
          // 保存生成的内容
          if (result && result.content) {
            await writeApi.saveContent(currentSession.id, result.content, 'quick')
          }
        } catch (e) {
          console.error('Stream reading error:', e)
          setOutputText('读取响应失败，请重试...')
        }
      } else {
        // 非流式处理
        const data = await response.json()
        console.log('Non-stream data:', data)
        setOutputText(data.content || 'No content')
        
        // 保存生成的内容
        if (data && data.content) {
          await writeApi.saveContent(currentSession.id, data.content, 'quick')
        }
      }
    } catch (error) {
      console.error('生成失败:', error)
      setOutputText('生成失败，请重试...')
    } finally {
      setIsGenerating(false)
    }
  }

  const handleClear = async () => {
    if (!currentSession) return
    
    try {
      // 调用后端API清空会话内容
      await writeApi.clearSessionContent(currentSession.id)
      console.log('后端内容已清空')
    } catch (error) {
      console.error('清空后端内容失败:', error)
      alert('清空失败，请重试')
      return
    }
    
    // 清除快速写作的模板化参数
    setTextType('')
    setArticleTitle('')
    setArticleLength('')
    setArticleStyle('')
    setOtherRequirements('')
    setOutputText('')
  }

  const handleCopy = () => {
    if (outputText) {
      navigator.clipboard.writeText(outputText)
        .then(() => alert('复制成功'))
        .catch(err => console.error('复制失败:', err))
    }
  }

  const handleAddReferenceClick = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    
    // 检查文件类型
    const allowedExtensions = ['.docx', '.md']
    const fileExtension = '.' + file.name.split('.').pop().toLowerCase()
    
    if (!allowedExtensions.includes(fileExtension)) {
      alert('不支持的文件类型，请上传.docx或.md文件')
      return
    }
    
    try {
      console.log('开始上传文件:', file.name)
      const response = await writeApi.uploadReference(file)
      console.log('上传响应完整数据:', JSON.stringify(response, null, 2))
      
      if (response && response.filename) {
        console.log('准备添加到参考文档列表:', response)
        setReferenceDocuments(prev => {
          const newDocs = [
            ...prev,
            {
              filename: response.filename,
              content: response.content,
              type: response.type
            }
          ]
          console.log('更新后的参考文档列表:', newDocs)
          return newDocs
        })
        alert('文档上传成功！')
      } else {
        console.error('响应格式不正确:', response)
        alert('文档上传失败，响应格式不正确')
      }
    } catch (error) {
      console.error('上传失败:', error)
      console.error('错误详情:', error.response?.data || error.message)
      alert(`文档上传失败: ${error.message || '未知错误'}`)
    }
    
    // 清空文件输入
    e.target.value = ''
  }

  const handleRemoveReference = (index) => {
    setReferenceDocuments(prev => prev.filter((_, i) => i !== index))
  }

  const handleExport = async (exportType) => {
    if (!currentSession || !outputText) {
      alert('没有可导出的内容')
      return
    }
    
    // 检查是否有文章标题
    if (!articleTitle || articleTitle.trim() === '') {
      alert('请填写文章标题')
      return
    }
    
    try {
      console.log(`开始导出为${exportType}格式`)
      
      // 如果导出docx，检查是否有docx参考文档
      let referenceDoc = null
      if (exportType === 'docx') {
        const docxReference = referenceDocuments.find(doc => doc.filename.endsWith('.docx'))
        if (docxReference) {
          referenceDoc = docxReference.filename
          console.log(`使用参考文档作为模板: ${referenceDoc}`)
        }
      }
      
      const blob = await writeApi.exportDocument(currentSession.id, exportType, referenceDoc)
      
      // 创建下载链接
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      
      // 生成文件名，使用文章标题
      const timestamp = new Date().toISOString().slice(0, 10).replace(/-/g, '')
      const extension = exportType === 'docx' ? 'docx' : 'md'
      link.download = `${articleTitle.trim()}_${timestamp}.${extension}`
      
      // 触发下载
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      
      // 释放URL对象
      window.URL.revokeObjectURL(url)
      
      console.log(`导出${exportType}成功`)
    } catch (error) {
      console.error('导出失败:', error)
      alert('导出失败，请重试')
    }
  }

  // 如果没有当前会话，不显示内容
  if (!currentSession) {
    return null
  }

  return (
    <div className="main-content">
      <div className="module-title">
        快速写作
      </div>
      
      {/* 快速写作的模板化UI */}
      <div className="input-area template-input">
        <div className="template-prompt">
          帮我写一篇
          <select
            value={textType}
            onChange={(e) => setTextType(e.target.value)}
            disabled={isGenerating}
            className="text-type-select"
            placeholder="输入文体"
          >
            <option value="">输入文体</option>
            <option value="议论文">议论文</option>
            <option value="记叙文">记叙文</option>
            <option value="说明文">说明文</option>
            <option value="散文">散文</option>
            <option value="公文">公文</option>
            <option value="报告">报告</option>
            <option value="演讲稿">演讲稿</option>
            <option value="新闻稿">新闻稿</option>
            <option value="产品文案">产品文案</option>
          </select>
          ，文章标题是
          <input
            type="text"
            value={articleTitle}
            onChange={(e) => setArticleTitle(e.target.value)}
            disabled={isGenerating}
            className="article-title-input"
            placeholder="输入标题（必填）"
          />
          ，文章篇幅
          <select
            value={articleLength}
            onChange={(e) => setArticleLength(e.target.value)}
            disabled={isGenerating}
            className="article-length-select"
            placeholder="请输入"
          >
            <option value="">请输入</option>
            <option value="300">300</option>
            <option value="500">500</option>
            <option value="800">800</option>
            <option value="1000">1000</option>
            <option value="1500">1500</option>
            <option value="2000">2000</option>
          </select>
          字左右，风格
          <select
            value={articleStyle}
            onChange={(e) => setArticleStyle(e.target.value)}
            disabled={isGenerating}
            className="article-style-select"
            placeholder="请输入"
          >
            <option value="">请输入</option>
            <option value="正式">正式</option>
            <option value="活泼">活泼</option>
            <option value="严肃">严肃</option>
            <option value="幽默">幽默</option>
            <option value="专业">专业</option>
            <option value="文艺">文艺</option>
            <option value="简洁">简洁</option>
            <option value="详细">详细</option>
          </select>
          ，其他要求
          <input
            type="text"
            value={otherRequirements}
            onChange={(e) => setOtherRequirements(e.target.value)}
            disabled={isGenerating}
            className="other-requirements-input"
            placeholder="请输入"
          />
          。
        </div>
        
        <div className="template-controls">
          <button className="add-reference-btn" onClick={handleAddReferenceClick}>+模板选择</button>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".docx,.md"
            style={{ display: 'none' }}
          />
          <div className="function-buttons">
            <button
              className="start-writing-btn"
              onClick={handleGenerate}
              disabled={isGenerating || !textType}
            >
              {isGenerating ? '生成中...' : '开始写作'}
            </button>
          </div>
        </div>
      </div>
      
      {/* 显示已上传的参考文档 */}
      {referenceDocuments.length > 0 && (
        <div className="reference-documents">
          <div className="reference-title">参考文档：</div>
          {referenceDocuments.map((doc, index) => (
            <div key={index} className="reference-item">
              <span className="reference-filename">{doc.filename}</span>
              <button 
                className="reference-remove-btn"
                onClick={() => handleRemoveReference(index)}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
      
      <div className="output-area">
        {outputText ? (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              h1: ({node, ...props}) => <h1 className="md-h1" {...props} />,
              h2: ({node, ...props}) => <h2 className="md-h2" {...props} />,
              h3: ({node, ...props}) => <h3 className="md-h3" {...props} />,
              h4: ({node, ...props}) => <h4 className="md-h4" {...props} />,
              h5: ({node, ...props}) => <h5 className="md-h5" {...props} />,
              h6: ({node, ...props}) => <h6 className="md-h6" {...props} />,
              p: ({node, ...props}) => <p className="md-p" {...props} />,
              ul: ({node, ...props}) => <ul className="md-ul" {...props} />,
              ol: ({node, ...props}) => <ol className="md-ol" {...props} />,
              li: ({node, ...props}) => <li className="md-li" {...props} />,
              blockquote: ({node, ...props}) => <blockquote className="md-blockquote" {...props} />,
              code: ({node, inline, ...props}) => 
                inline 
                  ? <code className="md-code-inline" {...props} />
                  : <code className="md-code-block" {...props} />,
              pre: ({node, ...props}) => <pre className="md-pre" {...props} />,
              table: ({node, ...props}) => <div className="md-table-wrapper"><table className="md-table" {...props} /></div>,
              thead: ({node, ...props}) => <thead className="md-thead" {...props} />,
              tbody: ({node, ...props}) => <tbody className="md-tbody" {...props} />,
              tr: ({node, ...props}) => <tr className="md-tr" {...props} />,
              th: ({node, ...props}) => <th className="md-th" {...props} />,
              td: ({node, ...props}) => <td className="md-td" {...props} />,
              a: ({node, ...props}) => <a className="md-a" {...props} />,
              strong: ({node, ...props}) => <strong className="md-strong" {...props} />,
              em: ({node, ...props}) => <em className="md-em" {...props} />,
              hr: ({node, ...props}) => <hr className="md-hr" {...props} />,
            }}
          >
            {outputText}
          </ReactMarkdown>
        ) : (
          '生成的内容将显示在这里...'
        )}
      </div>
      
      <div className="action-bar">
        <button className="action-btn" onClick={handleClear} disabled={isGenerating}>
          清空
        </button>
        <button className="action-btn" onClick={handleCopy} disabled={!outputText}>
          复制全文
        </button>
        <div className="export-buttons">
          <button 
            className="action-btn export-btn" 
            onClick={() => handleExport('md')} 
            disabled={!outputText}
          >
            导出MD
          </button>
          <button 
            className="action-btn export-btn" 
            onClick={() => handleExport('docx')} 
            disabled={!outputText}
          >
            导出DOCX
          </button>
        </div>
      </div>
    </div>
  )
}

export default MainContent
