import React, { useState, useRef, useEffect } from 'react'
import { writeApi } from '../api/writeApi'
import { uploadApi } from '../api/uploadApi'
import { generateApi } from '../api/generateApi'

function MainContent({ currentSession, currentOutput, editorContent, chatHistory, onArticleUpdate, onChatHistoryUpdate, quotes, onRemoveQuote, onClearQuotes }) {
  const [isGenerating, setIsGenerating] = useState(false)
  
  const [writingMode, setWritingMode] = useState('quick')
  
  const [templateType, setTemplateType] = useState('')
  const [quickRequirements, setQuickRequirements] = useState('')
  
  const [referenceDocuments, setReferenceDocuments] = useState([])
  const fileInputRef = useRef(null)
  
  // 文件上传状态：'idle' | 'uploading' | 'parsing' | 'completed' | 'error'
  const [uploadStatus, setUploadStatus] = useState('idle')
  const [uploadMessage, setUploadMessage] = useState('')
  const [uploadProgress, setUploadProgress] = useState(0)
  
  // 参考写作生成类型
  const [referenceWriteType, setReferenceWriteType] = useState('general')
  
  // 回函生成状态
  const [isGeneratingReply, setIsGeneratingReply] = useState(false)
  
  const [chatInput, setChatInput] = useState('')
  
  const [displayChatHistory, setDisplayChatHistory] = useState([])
  
  const getArticleContent = () => {
    return editorContent || currentOutput || ''
  }
  
  useEffect(() => {
    if (chatHistory && chatHistory.length > 0) {
      setDisplayChatHistory(chatHistory)
    } else {
      setDisplayChatHistory([])
    }
  }, [chatHistory])

  const replaceContentInArticle = (originalContent, oldText, newText) => {
    if (!originalContent.includes(oldText)) {
      console.warn('未找到要替换的原文内容')
      return originalContent
    }
    return originalContent.replace(oldText, newText)
  }

  const handleGenerate = async () => {
    if (!currentSession) return
    
    setIsGenerating(true)
    
    let userDisplayContent = ''
    
    const articleContent = getArticleContent()
    const isEditRequest = articleContent && quickRequirements && quickRequirements.trim()
    
    if (isEditRequest) {
      userDisplayContent = quickRequirements
    } else {
      if (templateType === 'notice') {
        userDisplayContent = quickRequirements ? `写通知：${quickRequirements}` : '写通知'
      } else if (templateType === 'regulation') {
        userDisplayContent = quickRequirements ? `写规章制度：${quickRequirements}` : '写规章制度'
      } else if (templateType === 'speech') {
        userDisplayContent = quickRequirements ? `写讲话稿：${quickRequirements}` : '写讲话稿'
      } else {
        userDisplayContent = quickRequirements ? `写文章：${quickRequirements}` : '写文章'
      }
    }
    
    const newChatHistory = [...displayChatHistory, {
      role: 'user',
      content: userDisplayContent
    }]
    setDisplayChatHistory(newChatHistory)
    writeApi.saveContent(currentSession.id, userDisplayContent, 'quick', 'chat', 'user').catch(() => {})
    
    try {
      // 收集结构化数据
      let ragContent = ''
      let ragReferences = []
      
      if (!isEditRequest) {
        // 生成新文章时，先调用知识库生成 API
        try {
          const topic = quickRequirements && quickRequirements.trim() 
            ? `${quickRequirements}`
            : (templateType === 'notice' ? '通知公文' : 
               templateType === 'regulation' ? '规章制度' : 
               templateType === 'speech' ? '讲话稿' : '文章')
          
          const requirements = quickRequirements || ''
          
          const generateResult = await generateApi.generateDocument(
            topic,
            requirements,
            'qwen3-235b',
            true,
            3
          )
          
          if (generateResult && generateResult.content) {
            ragContent = generateResult.content
            ragReferences = generateResult.references || []
            console.log('知识库生成成功，参考文献:', ragReferences)
          }
        } catch (error) {
          console.error('知识库生成失败:', error)
        }
      }
      
      // 构建引用内容列表
      const quoteList = quotes ? quotes.map(q => q.text) : []
      
      // 构建上传文档内容
      let refContent = ''
      let refFilename = ''
      if (referenceDocuments && referenceDocuments.length > 0) {
        const uploadDoc = referenceDocuments.find(doc => doc.type === 'upload')
        if (uploadDoc) {
          refContent = uploadDoc.content || ''
          refFilename = uploadDoc.filename || ''
        }
      }
      
      const url = '/api/write/quick'
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          session_id: currentSession.id,
          mode: isEditRequest ? 'edit' : 'quick',
          style: templateType || 'general',
          user_requirements: quickRequirements || '',
          reference_content: refContent,
          reference_filename: refFilename,
          rag_content: ragContent,
          rag_references: ragReferences,
          quotes: quoteList,
          article_content: isEditRequest ? articleContent : '',
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
        
        const extractArticleContent = (text) => {
          let articleContent = text
          const articleMatch = text.match(/---ARTICLE---\n?([\s\S]*?)(?=---SUMMARY---|$)/)
          if (articleMatch) {
            articleContent = articleMatch[1].trim()
          }
          return articleContent
        }
        
        try {
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
                      const articleContent = extractArticleContent(output)
                      if (onArticleUpdate) {
                        onArticleUpdate(currentSession.id, articleContent)
                      }
                    }
                  }
                } catch (e) {
                  console.error('Parse error:', e)
                }
              }
            }
          }
          
          if (output) {
            let articleContent = output
            let summaryContent = '已生成文章'
            
            const articleMatch = output.match(/---ARTICLE---\n?([\s\S]*?)(?=---SUMMARY---|$)/)
            const summaryMatch = output.match(/---SUMMARY---\n?([\s\S]*?)$/)
            
            if (articleMatch) {
              articleContent = articleMatch[1].trim()
            }
            if (summaryMatch) {
              summaryContent = summaryMatch[1].trim()
            }
            
            await writeApi.saveArticle(currentSession.id, articleContent)
            
            const updatedChatHistory = [...newChatHistory, {
              role: 'assistant',
              content: summaryContent
            }]
            setDisplayChatHistory(updatedChatHistory)
            
            await writeApi.saveContent(currentSession.id, summaryContent, 'quick', 'chat', 'assistant')
            
            if (onArticleUpdate) {
              onArticleUpdate(currentSession.id, articleContent)
            }
            if (onChatHistoryUpdate) {
              onChatHistoryUpdate(currentSession.id, updatedChatHistory)
            }
          }
        } catch (e) {
          console.error('Stream reading error:', e)
        }
      }
    } catch (error) {
      console.error('生成失败:', error)
    } finally {
      setIsGenerating(false)
      setQuickRequirements('')
      setTemplateType('')
      if (onClearQuotes) {
        onClearQuotes()
      }
    }
  }

  const handleClear = async () => {
    if (!currentSession) return
    
    try {
      await writeApi.clearSessionContent(currentSession.id)
    } catch (error) {
      console.error('清空后端内容失败:', error)
      alert('清空失败，请重试')
      return
    }
    
    setTemplateType('')
    setQuickRequirements('')
    setReferenceDocuments([])
  }

  const handleFileChange = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    
    if (!currentSession) {
      alert('请先选择或创建一个会话')
      return
    }
    
    const allowedExtensions = ['.pdf', '.docx', '.md', '.txt']
    const fileExtension = '.' + file.name.split('.').pop().toLowerCase()
    
    if (!allowedExtensions.includes(fileExtension)) {
      alert('不支持的文件类型，请上传 .pdf、.docx、.md 或 .txt 文件')
      return
    }
    
    // 重置状态并开始上传
    setUploadStatus('uploading')
    setUploadMessage('正在上传文件...')
    setUploadProgress(0)
    
    try {
      // 使用 uploadApi 上传文件，只解析不提取字段
      const fileData = await uploadApi.uploadFile(
        currentSession.id, 
        file, 
        true,   // auto_parse: 自动解析
        false   // auto_extract: 不自动提取字段
      )
      
      if (fileData && fileData.file_id) {
        // 上传成功，开始解析
        setUploadStatus('parsing')
        setUploadMessage('文件上传成功！正在解析文档内容...')
        setUploadProgress(70)
        
        // 模拟解析完成的延迟，给用户视觉反馈
        // 实际解析已经在后端完成，这里是为了显示效果
        await new Promise(resolve => setTimeout(resolve, 800))
        
        setUploadProgress(100)
        setUploadMessage('解析完成！')
        
        // 添加文件到参考文档列表
        setReferenceDocuments(prev => [
          ...prev,
          {
            filename: fileData.original_filename,
            content: fileData.parsed_content || '',
            type: 'upload',
            originalType: fileData.file_type
          }
        ])
        
        // 显示完成状态后，延迟重置
        setTimeout(() => {
          setUploadStatus('completed')
          setTimeout(() => {
            setUploadStatus('idle')
            setUploadMessage('')
            setUploadProgress(0)
          }, 2000)
        }, 500)
      } else {
        setUploadStatus('error')
        setUploadMessage('文档上传失败')
        setTimeout(() => {
          setUploadStatus('idle')
          setUploadMessage('')
          setUploadProgress(0)
        }, 3000)
      }
    } catch (error) {
      console.error('上传失败:', error)
      setUploadStatus('error')
      setUploadMessage(`上传失败: ${error.message || '未知错误'}`)
      setTimeout(() => {
        setUploadStatus('idle')
        setUploadMessage('')
        setUploadProgress(0)
      }, 3000)
    }
    
    e.target.value = ''
  }

  const handleRemoveReference = (index) => {
    setReferenceDocuments(prev => prev.filter((_, i) => i !== index))
  }

  const handleGenerateReply = async () => {
    const uploadDocs = referenceDocuments.filter(doc => doc.type === 'upload')
    if (uploadDocs.length === 0) return
    
    const doc = uploadDocs[0]
    setIsGeneratingReply(true)
    
    const newChatHistory = [...displayChatHistory, {
      role: 'user',
      content: `根据上传文件"${doc.filename}"生成回函`
    }]
    setDisplayChatHistory(newChatHistory)
    
    await writeApi.saveContent(currentSession?.id, `根据上传文件"${doc.filename}"生成回函`, 'reply', 'chat', 'user')
    
    try {
      const response = await fetch('/api/generate/reply', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          session_id: currentSession?.id,
          topic: doc.filename || '',
          requirements: '',
          original_content: doc.content || '',
          extracted_fields: {},
          model_name: 'qwen3-235b',
          use_knowledge_base: true,
          top_k: 3
        })
      })

      if (!response.body || !response.body.getReader) {
        const text = await response.text()
        throw new Error(text || '响应格式错误')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let replyContent = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        replyContent += decoder.decode(value, { stream: true })
      }

      let articleContent = replyContent
      let summaryContent = '已生成回函'
      
      const articleMatch = replyContent.match(/^---ARTICLE---\n?([\s\S]*?)---SUMMARY---/)
      const summaryMatch = replyContent.match(/---SUMMARY---\n?([\s\S]*?)$/)
      
      if (articleMatch) {
        articleContent = articleMatch[1].trim()
      } else {
        const fallbackMatch = replyContent.match(/^([\s\S]*?)---SUMMARY---/)
        if (fallbackMatch) {
          articleContent = fallbackMatch[1].trim()
        }
      }
      if (summaryMatch) {
        summaryContent = summaryMatch[1].trim()
      }
      
      await writeApi.saveArticle(currentSession?.id, articleContent)
      
      const updatedChatHistory = [...newChatHistory, {
        role: 'assistant',
        content: summaryContent
      }]
      setDisplayChatHistory(updatedChatHistory)
      
      await writeApi.saveContent(currentSession?.id, summaryContent, 'reply', 'chat', 'assistant')
      
      if (onArticleUpdate && currentSession?.id) {
        onArticleUpdate(currentSession.id, articleContent)
      }
      if (onChatHistoryUpdate) {
        onChatHistoryUpdate(currentSession.id, updatedChatHistory)
      }
    } catch (error) {
      console.error('生成回函失败:', error)
      alert('生成回函失败: ' + (error.message || '未知错误'))
    } finally {
      setIsGeneratingReply(false)
    }
  }

  const handleReferenceWrite = async () => {
    const uploadDocs = referenceDocuments.filter(doc => doc.type === 'upload')
    if (uploadDocs.length === 0) {
      alert('请先上传参考文档')
      return
    }

    const doc = uploadDocs[0]
    setIsGenerating(true)

    const typeLabels = {
      reply: '生成回函',
      imitate: '仿写公文',
      general: '基于内容生成'
    }
    const userMsgContent = referenceWriteType === 'reply'
      ? `根据上传文件"${doc.filename}"生成回函`
      : referenceWriteType === 'imitate'
        ? `仿照"${doc.filename}"的风格写一篇新公文`
        : `基于"${doc.filename}"的内容生成公文`
    
    const extraReq = chatInput.trim() ? `（要求：${chatInput.trim()}）` : ''

    const newChatHistory = [...displayChatHistory, {
      role: 'user',
      content: userMsgContent + extraReq
    }]
    setDisplayChatHistory(newChatHistory)
    writeApi.saveContent(currentSession?.id, userMsgContent + extraReq, 'reference', 'chat', 'user').catch(() => {})

    try {
      const response = await fetch('/api/generate/reference-write', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          session_id: currentSession?.id,
          reference_content: doc.content || '',
          reference_filename: doc.filename || '',
          generate_type: referenceWriteType,
          topic: chatInput.trim() || doc.filename || '',
          requirements: chatInput.trim() || '',
          model_name: 'qwen3-235b',
          use_knowledge_base: true,
          top_k: 3
        })
      })

      if (!response.body || !response.body.getReader) {
        const text = await response.text()
        throw new Error(text || '响应格式错误')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let fullContent = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        fullContent += decoder.decode(value, { stream: true })
      }

      let articleContent = fullContent
      let summaryContent = typeLabels[referenceWriteType] + '完成'

      const articleMatch = fullContent.match(/^---ARTICLE---\n?([\s\S]*?)---SUMMARY---/)
      const summaryMatch = fullContent.match(/---SUMMARY---\n?([\s\S]*?)$/)

      if (articleMatch) {
        articleContent = articleMatch[1].trim()
      } else {
        const fallbackMatch = fullContent.match(/^([\s\S]*?)---SUMMARY---/)
        if (fallbackMatch) {
          articleContent = fallbackMatch[1].trim()
        }
      }
      if (summaryMatch) {
        summaryContent = summaryMatch[1].trim()
      }

      await writeApi.saveArticle(currentSession?.id, articleContent)

      const updatedChatHistory = [...newChatHistory, {
        role: 'assistant',
        content: summaryContent
      }]
      setDisplayChatHistory(updatedChatHistory)

      await writeApi.saveContent(currentSession?.id, summaryContent, 'reference', 'chat', 'assistant')

      if (onArticleUpdate && currentSession?.id) {
        onArticleUpdate(currentSession.id, articleContent)
      }
      if (onChatHistoryUpdate) {
        onChatHistoryUpdate(currentSession.id, updatedChatHistory)
      }
    } catch (error) {
      console.error('参考写作失败:', error)
      alert('参考写作失败: ' + (error.message || '未知错误'))
    } finally {
      setIsGenerating(false)
      setChatInput('')
    }
  }

  const handleEditSubmit = async () => {
    if (!currentSession || !chatInput.trim()) {
      return
    }
    
    const articleContent = getArticleContent()
    if (!articleContent) {
      alert('请先生成文章内容，然后再进行修改润色')
      return
    }
    
    setIsGenerating(true)
    
    const hasQuotes = quotes && quotes.length > 0
    const originalQuotes = hasQuotes ? quotes.map(q => q.text) : []
    
    try {
      const userDisplayContent = chatInput
      
      const newChatHistory = [...displayChatHistory, {
        role: 'user',
        content: userDisplayContent
      }]
      setDisplayChatHistory(newChatHistory)
      
      writeApi.saveContent(currentSession.id, userDisplayContent, 'quick', 'chat', 'user').catch(() => {})
      
      const url = '/api/write/quick'
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            session_id: currentSession.id,
            mode: 'edit',
            style: templateType || 'general',
            user_requirements: chatInput.trim(),
            reference_content: '',
            reference_filename: '',
            rag_content: '',
            rag_references: [],
            quotes: originalQuotes,
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
        
        try {
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
                } catch (e) {
                  console.error('Parse error:', e)
                }
              }
            }
          }
          
          if (output) {
            let summaryContent = '已完成修改'
            
            let articleResult = output
            const articleMatch = output.match(/---ARTICLE---\n?([\s\S]*?)(?=---SUMMARY---|$)/)
            const summaryMatch = output.match(/---SUMMARY---\n?([\s\S]*?)$/)
            
            if (articleMatch) {
              articleResult = articleMatch[1].trim()
            }
            if (summaryMatch) {
              summaryContent = summaryMatch[1].trim()
            }
            
            await writeApi.saveArticle(currentSession.id, articleResult)
            
            if (onArticleUpdate) {
              onArticleUpdate(currentSession.id, articleResult)
            }
            
            const updatedChatHistory = [...newChatHistory, {
              role: 'assistant',
              content: summaryContent
            }]
            setDisplayChatHistory(updatedChatHistory)
            
            await writeApi.saveContent(currentSession.id, summaryContent, 'quick', 'chat', 'assistant')
            
            if (onChatHistoryUpdate) {
              onChatHistoryUpdate(currentSession.id, updatedChatHistory)
            }
          }
        } catch (e) {
          console.error('Stream reading error:', e)
        }
      }
    } catch (error) {
      console.error('修改失败:', error)
    } finally {
      setIsGenerating(false)
      setChatInput('')
      if (onClearQuotes) {
        onClearQuotes()
      }
    }
  }

  if (!currentSession) {
    return (
      <div className="main-content chatgpt-style">
        <div className="welcome-screen">
          <div className="welcome-title">AI 写作助手</div>
          <div className="welcome-subtitle">选择或创建一个会话开始写作</div>
        </div>
      </div>
    )
  }

  return (
    <div className="main-content chatgpt-style">
      <div className="chat-history">
        {displayChatHistory.map((message, index) => (
          <div key={index} className={`chat-message ${message.role}`}>
            <div className="message-content">
              <div className="message-header">
                <span className="message-role">
                  {message.role === 'user' ? '你' : 'AI'}
                </span>
              </div>
              <div className="message-text">
                {message.content}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="chat-input-container">
        {referenceDocuments.length > 0 && (
          <div className="reference-docs-bar">
            {referenceDocuments.map((doc, index) => (
              <div key={index} className={`reference-doc-chip ${doc.type === 'upload' ? 'upload-ref-chip' : 'kb-ref-chip'}`}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                </svg>
                <span className="doc-ref-label">{doc.type === 'upload' ? '上传参考' : '知识库参考'}</span>
                <span>{doc.filename}</span>
                {doc.originalType && doc.originalType !== 'md' && (
                  <span className="doc-type-badge">{doc.originalType.toUpperCase()}</span>
                )}
                {doc.type === 'upload' && (
                  <button onClick={() => handleRemoveReference(index)} className="chip-remove">×</button>
                )}
              </div>
            ))}
            {referenceDocuments.some(doc => doc.type === 'upload' && doc.content) && (
              <button
                className="reply-btn"
                onClick={handleGenerateReply}
                disabled={isGeneratingReply}
              >
                {isGeneratingReply ? '生成中...' : '生成回函'}
              </button>
            )}
          </div>
        )}
        
        {quotes && quotes.length > 0 && (
          <div className="reference-docs-bar quotes-bar">
            {quotes.map((quote) => (
              <div key={quote.id} className="reference-doc-chip quote-chip">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V21c0 1 0 1 1 1z"></path>
                  <path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2 4-3 0-3 .5-3 2v2c0 1 0 1 1 1z"></path>
                </svg>
                <span className="quote-preview" title={quote.text}>{quote.preview}</span>
                <button onClick={() => onRemoveQuote(quote.id)} className="chip-remove">×</button>
              </div>
            ))}
          </div>
        )}
        
        <div className="mode-selector-bar">
          <button 
            className={`mode-chip ${writingMode === 'quick' ? 'active' : ''}`}
            onClick={() => setWritingMode('quick')}
          >
            快速写作
          </button>
          <button 
            className={`mode-chip ${writingMode === 'reference' ? 'active' : ''}`}
            onClick={() => setWritingMode('reference')}
          >
            参考写作
          </button>
          <button 
            className={`mode-chip ${writingMode === 'edit' ? 'active' : ''}`}
            onClick={() => setWritingMode('edit')}
          >
            修改润色
          </button>
        </div>

        <div className="chat-input-box">
          {writingMode === 'quick' && (
            <div className="quick-writing-inputs">
              <div className="input-row">
                <div className="template-selector">
                  <div className="template-options">
                    {[
                      { value: '', label: '通用公文', desc: '适用于一般性公文写作，格式灵活通用' },
                      { value: 'notice', label: '通知', desc: '适用于发布规章制度、传达事项，如"关于XXX的通知"' },
                      { value: 'regulation', label: '规章制度', desc: '适用于制定管理办法、实施细则，分章节条款' },
                      { value: 'speech', label: '讲话稿', desc: '适用于会议讲话、致辞，需开场问候和层次递进' },
                    ].map(t => (
                      <div
                        key={t.value}
                        className={`template-option ${templateType === t.value ? 'active' : ''}`}
                        onClick={() => !isGenerating && setTemplateType(t.value)}
                      >
                        <div className="template-label">{t.label}</div>
                        <div className="template-desc">{t.desc}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <textarea
                value={quickRequirements}
                onChange={(e) => setQuickRequirements(e.target.value)}
                disabled={isGenerating}
                className="chat-textarea"
                placeholder="请输入写作要求..."
                rows={3}
              />
            </div>
          )}

          {writingMode === 'edit' && (
            <div className="edit-writing-inputs">
              <div className="input-row">
                <textarea
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  disabled={isGenerating}
                  className="chat-textarea"
                  placeholder={quotes && quotes.length > 0 
                    ? "输入对选中内容的修改要求（仅修改选中部分）..." 
                    : "输入修改要求（全文修改）..."}
                  rows={3}
                />
              </div>
            </div>
          )}

          {writingMode === 'reference' && (
            <div className="reference-writing-inputs">
              <div className="input-row">
                <div className="reference-write-type-selector">
                  <div className="ref-write-options">
                    {[
                      { value: 'reply', label: '生成回函', desc: '根据上传文件内容生成正式回函' },
                      { value: 'imitate', label: '仿写公文', desc: '学习上传文件的风格和结构，写新主题公文' },
                      { value: 'general', label: '基于内容生成', desc: '基于上传文件内容生成相关公文' },
                    ].map(t => (
                      <div
                        key={t.value}
                        className={`ref-write-option ${referenceWriteType === t.value ? 'active' : ''}`}
                        onClick={() => !isGenerating && setReferenceWriteType(t.value)}
                      >
                        <div className="ref-write-label">{t.label}</div>
                        <div className="ref-write-desc">{t.desc}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <textarea
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                disabled={isGenerating}
                className="chat-textarea"
                placeholder={referenceDocuments.filter(d => d.type === 'upload').length > 0
                  ? "输入补充要求（可选），AI将基于参考文件生成..."
                  : "请先上传参考文档"}
                rows={3}
              />
            </div>
          )}

          <div className="chat-actions">
            <button 
              className="chat-action-btn upload-btn"
              onClick={() => fileInputRef.current?.click()}
              title="上传参考文档"
              disabled={uploadStatus !== 'idle'}
            >
              {uploadStatus !== 'idle' ? '处理中...' : '上传文件'}
            </button>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept=".docx,.md,.txt,.pdf"
              style={{ display: 'none' }}
              disabled={uploadStatus !== 'idle'}
            />
            <button 
              className="chat-action-btn send-btn"
              onClick={writingMode === 'edit' ? handleEditSubmit : writingMode === 'reference' ? handleReferenceWrite : handleGenerate}
              disabled={isGenerating || (writingMode === 'edit' && !chatInput.trim()) || (writingMode === 'reference' && referenceDocuments.filter(d => d.type === 'upload').length === 0) || uploadStatus !== 'idle'}
            >
              {isGenerating ? '生成中...' : '发送'}
            </button>
          </div>

          {/* 文件上传进度提示 */}
          {uploadStatus !== 'idle' && (
            <div className={`upload-status-container ${uploadStatus}`}>
              <div className="upload-progress-wrapper">
                <div className="upload-spinner"></div>
                <div className="upload-info">
                  <div className="upload-message">{uploadMessage}</div>
                  <div className="upload-progress-bar">
                    <div 
                      className="upload-progress-fill" 
                      style={{ width: `${uploadProgress}%` }}
                    ></div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
      
    </div>
  )
}

export default MainContent
