import { useState, useEffect, useRef } from 'react'
import './App.css'
import TopNav from './components/TopNav'
import Sidebar from './components/Sidebar'
import MainContent from './components/MainContent'
import EditorSidebar from './components/EditorSidebar'
import { sessionApi } from './api/sessionApi'
import { writeApi } from './api/writeApi'

function App() {
  // 当前选中的会话ID
  const [currentSession, setCurrentSession] = useState(null)
  // 所有会话列表
  const [sessions, setSessions] = useState([])
  
  // 存储每个会话的内容，键为会话ID
  const [sessionContents, setSessionContents] = useState({})
  
  // 当前会话的输出内容（文章主体）
  const [currentSessionOutput, setCurrentSessionOutput] = useState('')
  
  // 编辑器中的实时内容（用于确保AI使用最新的编辑器内容）
  const [editorRealtimeContent, setEditorRealtimeContent] = useState('')
  
  // 当前会话的对话历史
  const [currentChatHistory, setCurrentChatHistory] = useState([])
  
  // 当前会话的引用列表
  const [currentQuotes, setCurrentQuotes] = useState([])
  
  // 用于跟踪组件是否已挂载，避免竞态条件
  const isMountedRef = useRef(true)
  const isLoadingRef = useRef(false)
  
  // 左侧栏显示状态
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => {
    // 从localStorage恢复侧边栏状态
    const savedState = localStorage.getItem('isSidebarOpen')
    return savedState !== null ? savedState === 'true' : true
  })
  
  // 加载会话列表
  const loadSessions = async () => {
    // 防止重复调用
    if (isLoadingRef.current) {
      console.log('loadSessions already in progress, skipping')
      return
    }
    isLoadingRef.current = true
    
    try {
      const response = await sessionApi.getSessions()
      console.log('loadSessions response:', response)
      
      // 检查组件是否仍然挂载
      if (!isMountedRef.current) {
        console.log('Component unmounted, skipping state update')
        return
      }
      
      if (response && Array.isArray(response)) {
        const sessionList = response.map(session => ({
          id: session.session_id,
          name: session.session_name,
          updatedAt: new Date(session.created_at).toLocaleString()
        }))
        setSessions(sessionList)
        console.log('sessionList:', sessionList)
        
        // 获取localStorage中保存的当前会话ID
        const savedSessionId = localStorage.getItem('currentSessionId')
        console.log('savedSessionId:', savedSessionId)
        
        if (sessionList.length > 0) {
          if (savedSessionId) {
            // 查找与保存的ID匹配的会话
            const savedSession = sessionList.find(session => session.id === parseInt(savedSessionId))
            if (savedSession) {
              console.log('Setting currentSession to savedSession:', savedSession)
              setCurrentSession(savedSession)
              return
            }
          }
          // 如果没有保存的会话ID或找不到匹配的会话，默认选中第一个
          console.log('Setting currentSession to first session:', sessionList[0])
          setCurrentSession(sessionList[0])
        }
        // 如果没有会话，清空当前会话
        else if (sessionList.length === 0) {
          setCurrentSession(null)
        }
      }
    } catch (error) {
      console.error('加载会话列表失败:', error)
    } finally {
      isLoadingRef.current = false
    }
  }
  
  // 加载会话内容
  const loadSessionContent = async (sessionId) => {
    console.log('loadSessionContent called with sessionId:', sessionId)
    try {
      console.log('Calling getArticle API with sessionId:', sessionId)
      const articleResponse = await writeApi.getArticle(sessionId)
      console.log('getArticle response:', articleResponse)
      if (articleResponse && articleResponse.article_content) {
        setCurrentSessionOutput(articleResponse.article_content)
      } else {
        setCurrentSessionOutput('')
      }
      
      console.log('Calling getSessionContent API with sessionId:', sessionId)
      const chatResponse = await writeApi.getSessionContent(sessionId)
      console.log('getSessionContent response:', chatResponse)
      if (chatResponse && chatResponse.length > 0) {
        setCurrentChatHistory(chatResponse.map(item => ({
          role: item.role,
          content: item.content
        })))
      } else {
        setCurrentChatHistory([])
      }
    } catch (error) {
      console.error('加载会话内容失败:', error)
      setCurrentSessionOutput('')
      setCurrentChatHistory([])
    }
  }
  
  // 组件挂载时加载会话列表
  useEffect(() => {
    isMountedRef.current = true
    loadSessions()
    return () => {
      isMountedRef.current = false
    }
  }, [])
  
  // 当前会话变化时加载会话内容
  useEffect(() => {
    if (currentSession && currentSession.id) {
      console.log('Current session changed, loading content for session:', currentSession.id)
      loadSessionContent(currentSession.id)
      setCurrentQuotes([])
    }
  }, [currentSession])
  
  // 保存侧边栏状态到localStorage
  useEffect(() => {
    localStorage.setItem('isSidebarOpen', isSidebarOpen)
  }, [isSidebarOpen])

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
    localStorage.setItem('currentSessionId', session.id)
  }
  
  // 处理文章内容更新
  const handleArticleUpdate = async (sessionId, content) => {
    if (sessionId === currentSession?.id) {
      setCurrentSessionOutput(content)
      try {
        await writeApi.saveArticle(sessionId, content)
        console.log('文章内容已保存到后端')
      } catch (error) {
        console.error('保存文章内容失败:', error)
      }
    }
  }
  
  // 处理对话历史更新
  const handleChatHistoryUpdate = (sessionId, chatHistory) => {
    if (sessionId === currentSession.id) {
      setCurrentChatHistory(chatHistory)
    }
  }
  
  // 处理添加引用
  const handleAddQuote = (text, matchResult) => {
    const newQuote = {
      id: Date.now(),
      text: text,
      preview: text.length > 30 ? text.substring(0, 30) + '...' : text,
      match: matchResult
    }
    setCurrentQuotes(prev => [...prev, newQuote])
  }
  
  // 处理删除引用
  const handleRemoveQuote = (quoteId) => {
    setCurrentQuotes(prev => prev.filter(q => q.id !== quoteId))
  }
  
  // 处理清空引用
  const handleClearQuotes = () => {
    setCurrentQuotes([])
  }
  
  // 处理编辑器内容实时变化
  const handleEditorContentChange = (content) => {
    setEditorRealtimeContent(content)
  }

  return (
    <div className="app-container">
      <TopNav />
      <div className={`main-layout ${isSidebarOpen ? '' : 'sidebar-closed'}`}>
        <Sidebar 
          sessions={sessions} 
          currentSession={currentSession} 
          onSessionChange={handleSessionChange} 
          onNewSession={handleNewSession} 
          onDeleteSession={handleDeleteSession} 
          onRenameSession={handleRenameSession}
          isOpen={isSidebarOpen}
        />
        {currentSession ? (
          <>
            <EditorSidebar 
              currentSession={currentSession}
              currentOutput={currentSessionOutput}
              onArticleUpdate={handleArticleUpdate}
              onAddQuote={handleAddQuote}
              onEditorContentChange={handleEditorContentChange}
            />
            <MainContent 
              currentSession={currentSession}
              currentOutput={currentSessionOutput}
              editorContent={editorRealtimeContent}
              chatHistory={currentChatHistory}
              onArticleUpdate={handleArticleUpdate}
              onChatHistoryUpdate={handleChatHistoryUpdate}
              quotes={currentQuotes}
              onRemoveQuote={handleRemoveQuote}
              onClearQuotes={handleClearQuotes}
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
