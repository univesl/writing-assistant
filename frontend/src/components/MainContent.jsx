import React, { useState, useEffect } from 'react'
import AgentRunPanel from './AgentRunPanel'

function MainContent({
  currentSession,
  editorContent,
  chatHistory,
  isBusy = false,
  agentRun,
  agentEvents = [],
  onAgentCancel,
  onAgentRetry,
  onAgentMessage,
}) {
  const [chatInput, setChatInput] = useState('')
  const [displayChatHistory, setDisplayChatHistory] = useState([])
  const currentSessionId = currentSession?.id || null

  useEffect(() => {
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

    try {
      await onAgentMessage?.(chatInput.trim())
      setChatInput('')
    } catch (error) {
      console.error('修改失败:', error)
      alert(error.message || 'Agent 任务创建失败')
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
      <div className="conversation-header">
        <strong>写作对话</strong>
        <span>通过对话生成或提出正文修改</span>
      </div>
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
        {agentRun && (
          <details className="agent-details" open={['queued', 'running'].includes(agentRun.status)}>
            <summary>运行详情</summary>
            <AgentRunPanel
              run={agentRun}
              events={agentEvents}
              onCancel={onAgentCancel}
              onRetry={onAgentRetry}
            />
          </details>
        )}
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
                placeholder={editorContent ? '描述希望如何修改正文…' : '描述需要起草的公文…'}
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
              {isBusy ? '处理中…' : '发送'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default MainContent
