import { useState } from 'react'

function Sidebar({ sessions, currentSession, onSessionChange, onNewSession, onDeleteSession, onRenameSession }) {
  const [renameMode, setRenameMode] = useState(null)
  const [renameInput, setRenameInput] = useState('')

  const handleNewSession = () => {
    // 调用父组件传递的创建会话函数
    onNewSession()
  }

  const handleRenameClick = (sessionId, sessionName) => {
    setRenameMode(sessionId)
    setRenameInput(sessionName)
  }

  const handleRenameSave = (sessionId) => {
    if (renameInput.trim()) {
      onRenameSession(sessionId, renameInput.trim())
      setRenameMode(null)
      setRenameInput('')
    }
  }

  const handleRenameCancel = () => {
    setRenameMode(null)
    setRenameInput('')
  }

  const handleDeleteClick = (sessionId) => {
    onDeleteSession(sessionId)
  }

  return (
    <div className="sidebar">
      <button className="new-session-btn" onClick={handleNewSession}>
        + 新建会话
      </button>
      <div className="session-list">
        {sessions.map(session => (
          <div
            key={session.id}
            className={`session-item ${session.id === (currentSession?.id || '') ? 'active' : ''}`}
            onClick={() => onSessionChange(session)}
          >
            {renameMode === session.id ? (
              <div className="session-name-edit">
                <input
                  type="text"
                  value={renameInput}
                  onChange={(e) => setRenameInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleRenameSave(session.id)}
                  autoFocus
                />
                <div className="rename-buttons">
                  <button onClick={(e) => {
                    e.stopPropagation()
                    handleRenameSave(session.id)
                  }}>保存</button>
                  <button onClick={(e) => {
                    e.stopPropagation()
                    handleRenameCancel()
                  }}>取消</button>
                </div>
              </div>
            ) : (
              <div className="session-name">
                {session.name}
                <div className="session-actions">
                  <button 
                    className="action-btn rename-btn"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleRenameClick(session.id, session.name)
                    }}
                    title="重命名"
                  >
                    ✏️
                  </button>
                  <button 
                    className="action-btn delete-btn"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDeleteClick(session.id)
                    }}
                    title="删除"
                  >
                    🗑️
                  </button>
                </div>
              </div>
            )}
            <div className="session-time">{session.updatedAt}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default Sidebar