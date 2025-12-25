import { useState, useEffect } from 'react'
import './App.css'
import TopNav from './components/TopNav'
import Sidebar from './components/Sidebar'
import MainContent from './components/MainContent'
import RightPanel from './components/RightPanel'
import { sessionApi } from './api/sessionApi'
import { writeApi } from './api/writeApi'

function App() {
  // 当前选中的功能模块：quick/write/step/polish
  const [activeModule, setActiveModule] = useState('quick')
  // 当前选中的会话ID
  const [currentSession, setCurrentSession] = useState(null)
  // 所有会话列表
  const [sessions, setSessions] = useState([])
  
  // 存储每个会话的内容，键为会话ID
  const [sessionContents, setSessionContents] = useState({})
  
  // 当前会话的输出内容
  const [currentSessionOutput, setCurrentSessionOutput] = useState('')
  // 步骤式写作参数
  const [stepParams, setStepParams] = useState({
    productName: '',
    sellingPoints: '',
    style: 'simple',
    length: 'medium'
  })
  // 校对润色参数
  const [polishParams, setPolishParams] = useState({
    polishType: 'check'
  })
  
  // 加载会话列表
  const loadSessions = async () => {
    try {
      const response = await sessionApi.getSessions()
      if (response && Array.isArray(response)) {
        const sessionList = response.map(session => ({
          id: session.session_id,
          name: session.session_name,
          updatedAt: new Date(session.created_at).toLocaleString()
        }))
        setSessions(sessionList)
        
        // 获取localStorage中保存的当前会话ID
        const savedSessionId = localStorage.getItem('currentSessionId')
        
        if (sessionList.length > 0) {
          if (savedSessionId) {
            // 查找与保存的ID匹配的会话
            const savedSession = sessionList.find(session => session.id === parseInt(savedSessionId))
            if (savedSession) {
              setCurrentSession(savedSession)
              return
            }
          }
          // 如果没有保存的会话ID或找不到匹配的会话，默认选中第一个
          if (!currentSession) {
            setCurrentSession(sessionList[0])
          }
        }
        // 如果没有会话，清空当前会话
        else if (sessionList.length === 0) {
          setCurrentSession(null)
        }
      }
    } catch (error) {
      console.error('加载会话列表失败:', error)
      // 如果加载失败，保持当前状态不变
    }
  }
  
  // 加载会话内容
  const loadSessionContent = async (sessionId) => {
    try {
      const contents = await writeApi.getSessionContent(sessionId)
      if (contents && contents.length > 0) {
        // 取最新的内容作为当前输出
        const latestContent = contents[contents.length - 1]
        setCurrentSessionOutput(latestContent.content)
        
        // 更新会话内容存储
        setSessionContents(prev => ({
          ...prev,
          [sessionId]: contents
        }))
      } else {
        // 如果没有内容，清空当前输出
        setCurrentSessionOutput('')
        setSessionContents(prev => ({
          ...prev,
          [sessionId]: []
        }))
      }
    } catch (error) {
      console.error('加载会话内容失败:', error)
      // 如果加载失败，使用本地存储的内容（如果有）
      const storedContent = sessionContents[sessionId]
      if (storedContent && storedContent.length > 0) {
        setCurrentSessionOutput(storedContent[storedContent.length - 1].content)
      } else {
        setCurrentSessionOutput('')
      }
    }
  }
  
  // 组件挂载时加载会话列表
  useEffect(() => {
    loadSessions()
  }, [])
  
  // 当前会话变化时加载会话内容
  useEffect(() => {
    if (currentSession && currentSession.id) {
      loadSessionContent(currentSession.id)
    }
  }, [currentSession])

  // 处理新建会话
  const handleNewSession = async () => {
    try {
      // 调用后端API创建新会话
      const response = await sessionApi.createSession('新会话')
      const newSession = {
        id: response.session_id,
        name: response.session_name,
        updatedAt: response.created_at
      }
      
      // 更新会话列表
      setSessions([newSession, ...sessions])
      
      // 设置当前会话为新创建的会话
      setCurrentSession(newSession)
      // 保存当前会话ID到localStorage
      localStorage.setItem('currentSessionId', newSession.id)
    } catch (error) {
      console.error('创建会话失败:', error)
      // 失败时使用本地模拟数据
      const mockSession = {
        id: Date.now(),
        name: '新会话',
        updatedAt: new Date().toLocaleString()
      }
      setSessions([mockSession, ...sessions])
      setCurrentSession(mockSession)
      // 保存当前会话ID到localStorage
      localStorage.setItem('currentSessionId', mockSession.id)
    }
  }

  // 处理删除会话
  const handleDeleteSession = async (sessionId) => {
    try {
      // 调用后端API删除会话
      await sessionApi.deleteSession(sessionId)
      
      // 更新会话列表
      const updatedSessions = sessions.filter(session => session.id !== sessionId)
      setSessions(updatedSessions)
      
      // 如果删除的是当前会话，设置新的当前会话
      if (currentSession.id === sessionId) {
        if (updatedSessions.length > 0) {
          setCurrentSession(updatedSessions[0])
          // 保存新的当前会话ID到localStorage
          localStorage.setItem('currentSessionId', updatedSessions[0].id)
        } else {
          // 如果删除了最后一个会话，清空当前会话
          setCurrentSession(null)
          // 从localStorage中删除当前会话ID
          localStorage.removeItem('currentSessionId')
        }
      }
    } catch (error) {
      console.error('删除会话失败:', error)
      // 失败时使用本地模拟删除
      const updatedSessions = sessions.filter(session => session.id !== sessionId)
      setSessions(updatedSessions)
      
      if (currentSession.id === sessionId) {
        if (updatedSessions.length > 0) {
          setCurrentSession(updatedSessions[0])
          // 保存新的当前会话ID到localStorage
          localStorage.setItem('currentSessionId', updatedSessions[0].id)
        } else {
          // 如果删除了最后一个会话，清空当前会话
          setCurrentSession(null)
          // 从localStorage中删除当前会话ID
          localStorage.removeItem('currentSessionId')
        }
      }
    }
  }

  // 处理重命名会话
  const handleRenameSession = async (sessionId, newName) => {
    try {
      // 调用后端API重命名会话
      await sessionApi.renameSession(sessionId, newName)
      
      // 更新会话列表
      const updatedSessions = sessions.map(session => {
        if (session.id === sessionId) {
          return { ...session, name: newName }
        }
        return session
      })
      setSessions(updatedSessions)
      
      // 如果重命名的是当前会话，更新当前会话
      if (currentSession.id === sessionId) {
        setCurrentSession({ ...currentSession, name: newName })
      }
    } catch (error) {
      console.error('重命名会话失败:', error)
      // 失败时使用本地模拟重命名
      const updatedSessions = sessions.map(session => {
        if (session.id === sessionId) {
          return { ...session, name: newName }
        }
        return session
      })
      setSessions(updatedSessions)
      
      if (currentSession.id === sessionId) {
        setCurrentSession({ ...currentSession, name: newName })
      }
    }
  }

  // 处理会话切换
  const handleSessionChange = (session) => {
    setCurrentSession(session)
    // 保存当前会话ID到localStorage
    localStorage.setItem('currentSessionId', session.id)
  }
  
  // 处理内容更新
  const handleContentUpdate = (sessionId, content) => {
    // 更新当前会话的输出内容
    if (sessionId === currentSession.id) {
      setCurrentSessionOutput(content)
    }
    
    // 更新会话内容存储
    setSessionContents(prev => {
      const sessionContentsList = prev[sessionId] || []
      return {
        ...prev,
        [sessionId]: [...sessionContentsList, {
          content_id: Date.now(), // 使用时间戳作为临时ID
          content: content,
          content_type: activeModule,
          created_at: new Date().toLocaleString()
        }]
      }
    })
  }

  return (
    <div className="app-container">
      <TopNav />
      <div className="main-layout">
        <Sidebar 
          sessions={sessions} 
          currentSession={currentSession} 
          onSessionChange={handleSessionChange} 
          onNewSession={handleNewSession} 
          onDeleteSession={handleDeleteSession} 
          onRenameSession={handleRenameSession} 
        />
        {currentSession ? (
          <>
            <MainContent 
              activeModule={activeModule} 
              currentSession={currentSession}
              stepParams={stepParams}
              polishParams={polishParams}
              currentOutput={currentSessionOutput}
              onContentUpdate={handleContentUpdate}
            />
            <RightPanel 
              activeModule={activeModule} 
              onModuleChange={setActiveModule} 
              stepParams={stepParams}
              onStepParamsChange={setStepParams}
              polishParams={polishParams}
              onPolishParamsChange={setPolishParams}
              currentSession={currentSession}
            />
          </>
        ) : (
          <div className="empty-session-message">
            请创建会话
          </div>
        )}
      </div>
    </div>
  )
}

export default App
