import React, { useState, useEffect } from 'react'
import AgentRunPanel from '../agent/AgentRunPanel'
import { isActiveAgentRun } from '../../utils/agentRun'

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
  const [agentDetailsOpen, setAgentDetailsOpen] = useState(false)
  const currentSessionId = currentSession?.id || null
  const agentActive = isActiveAgentRun(agentRun)

  useEffect(() => {
    if (chatHistory && chatHistory.length > 0) {
      setDisplayChatHistory(chatHistory)
    } else {
      setDisplayChatHistory([])
    }
  }, [chatHistory, currentSessionId])

  // 打开运行详情承载实时状态，避免页面顶部出现独立的加载浮层。
  useEffect(() => {
    if (agentActive) setAgentDetailsOpen(true)
  }, [agentActive, agentRun?.run_id])

  const lastUserMessageIndex = displayChatHistory
    .map(message => message.role === 'user')
    .lastIndexOf(true)

  const renderAgentDetails = () => {
    if (!agentRun) return null
    return (
      <details
        className="agent-details"
        open={agentDetailsOpen}
        onToggle={(event) => setAgentDetailsOpen(event.currentTarget.open)}
      >
        <summary>
          {agentActive && <span className="agent-details-spinner" aria-hidden="true" />}
          <span>运行详情</span>
          {agentActive && <span className="agent-details-status">运行中</span>}
        </summary>
        <AgentRunPanel
          run={agentRun}
          events={agentEvents}
          onCancel={onAgentCancel}
          onRetry={onAgentRetry}
        />
      </details>
    )
  }

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
          <React.Fragment key={`message-${index}`}>
            <div className={`chat-message ${message.role}`}>
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
            {agentRun && index === lastUserMessageIndex && renderAgentDetails()}
          </React.Fragment>
        ))}
        {agentRun && lastUserMessageIndex < 0 && renderAgentDetails()}
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
