import React, { useState, useRef, useEffect } from 'react'
import { writeApi } from '../api/writeApi'
import { streamQuickWrite } from '../services/writeStream'

function MainContent({
  currentSession,
  editorContent,
  chatHistory,
  onArticleUpdate,
  onChatHistoryUpdate,
  isBusy = false,
  onTaskStart,
  onTaskFinish,
}) {
  const [chatInput, setChatInput] = useState('')
  const [displayChatHistory, setDisplayChatHistory] = useState([])
  const currentSessionId = currentSession?.id || null
  const currentSessionIdRef = useRef(currentSession?.id || null)

  const getArticleContent = () => {
    return editorContent || ''
  }

  useEffect(() => {
    currentSessionIdRef.current = currentSessionId

    if (chatHistory && chatHistory.length > 0) {
      setDisplayChatHistory(chatHistory)
    } else {
      setDisplayChatHistory([])
    }
  }, [chatHistory, currentSessionId])

  const handleEditSubmit = async () => {
    if (!currentSession || isBusy || !chatInput.trim()) {
      return
    }

    const articleContent = getArticleContent()
    if (!articleContent) {
      alert('请先生成文章内容，然后再进行修改润色')
      return
    }

    const editSessionId = currentSession.id
    const operationId = onTaskStart
      ? onTaskStart(editSessionId, 'full-edit', '正在全文改写，请稍候…')
      : `local-${Date.now()}`
    if (!operationId) return

    try {
      const userDisplayContent = chatInput

      const newChatHistory = [...displayChatHistory, {
        role: 'user',
        content: userDisplayContent
      }]
      setDisplayChatHistory(newChatHistory)

      writeApi.saveContent(editSessionId, userDisplayContent, 'quick', 'chat', 'user').catch(() => {})

      const { articleContent: articleResult, summaryContent } = await streamQuickWrite({
        payload: {
          session_id: editSessionId,
          mode: 'edit',
          style: 'general',
          user_requirements: chatInput.trim(),
          reference_content: '',
          reference_filename: '',
          rag_content: '',
          rag_references: [],
          quotes: [],
          article_content: articleContent,
          extracted_fields: {},
          model_type: 'general',
          llm_model: 'qwen'
        },
        fallbackSummary: '已完成修改',
        onArticle: (liveArticle) => {
          if (editSessionId === currentSessionIdRef.current && onArticleUpdate) {
            onArticleUpdate(editSessionId, liveArticle, { persist: false })
          }
        },
      })

      await writeApi.saveArticle(editSessionId, articleResult)

      if (onArticleUpdate && editSessionId === currentSessionIdRef.current) {
        onArticleUpdate(editSessionId, articleResult, { persist: false })
      }

      const updatedChatHistory = [...newChatHistory, {
        role: 'assistant',
        content: summaryContent
      }]

      await writeApi.saveContent(editSessionId, summaryContent, 'quick', 'chat', 'assistant')

      if (editSessionId === currentSessionIdRef.current) {
        setDisplayChatHistory(updatedChatHistory)
        if (onChatHistoryUpdate) {
          onChatHistoryUpdate(editSessionId, updatedChatHistory)
        }
      }
    } catch (error) {
      console.error('修改失败:', error)
    } finally {
      onTaskFinish?.(editSessionId, operationId)
      setChatInput('')
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
        <div className="chat-input-box">
          <div className="edit-writing-inputs">
            <div className="input-row">
              <textarea
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                disabled={isBusy}
                className="chat-textarea"
                placeholder="输入全文改写要求（将重写整篇文章）..."
                rows={3}
              />
            </div>
          </div>

          <div className="chat-actions">
            <button
              className="chat-action-btn send-btn"
              onClick={handleEditSubmit}
              disabled={isBusy || !chatInput.trim()}
            >
              {isBusy ? '全文改写中...' : '全文改写'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default MainContent
