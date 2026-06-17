import { useState, useEffect, useRef } from 'react'
import './App.css'
import TopNav from './components/TopNav'
import Sidebar from './components/Sidebar'
import MainContent from './components/MainContent'
import EditorSidebar from './components/EditorSidebar'
import StartPage from './components/StartPage'
import { sessionApi } from './api/sessionApi'
import { writeApi } from './api/writeApi'

function App() {
  // 当前选中的会话ID
  const [currentSession, setCurrentSession] = useState(null)
  // 所有会话列表
  const [sessions, setSessions] = useState([])

  // 当前页面：'start' = 开始页面，'content' = 编辑页面
  // 从 localStorage 恢复页面状态，默认 start
  const [currentPage, setCurrentPage] = useState(() => {
    return localStorage.getItem('currentPage') || 'start'
  })

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

  // 生成中状态
  const [isGenerating, setIsGenerating] = useState(false)

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
      const [articleResponse, chatResponse] = await Promise.all([
        writeApi.getArticle(sessionId),
        writeApi.getSessionContent(sessionId)
      ])

      if (articleResponse && articleResponse.article_content) {
        setCurrentSessionOutput(articleResponse.article_content)
        // 会话有文章内容时自动切换到内容页
        setCurrentPage('content')
        localStorage.setItem('currentPage', 'content')
      } else {
        setCurrentSessionOutput('')
      }

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
      // 切换到开始页面
      setCurrentPage('start')
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
      setCurrentPage('start')
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
          setCurrentPage('start')
        } else {
          // 如果删除了最后一个会话，清空当前会话
          setCurrentSession(null)
          // 从localStorage中删除当前会话ID
          localStorage.removeItem('currentSessionId')
          setCurrentPage('start')
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
          setCurrentPage('start')
        } else {
          // 如果删除了最后一个会话，清空当前会话
          setCurrentSession(null)
          // 从localStorage中删除当前会话ID
          localStorage.removeItem('currentSessionId')
          setCurrentPage('start')
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

  // 处理从 StartPage 发起的生成请求
  const handleStartGeneration = async (config) => {
    if (!currentSession || isGenerating) return
    setIsGenerating(true)

    try {
      const DEFAULT_MODEL = 'Qwen2.5-72B-Instruct'
      const { writingMode, templateType, quickRequirements, referenceDocuments, referenceWriteType, referenceRequirements } = config

      // 构建用户显示内容
      let userDisplayContent = ''
      if (writingMode === 'quick') {
        if (templateType === 'notice') {
          userDisplayContent = quickRequirements ? `写通知：${quickRequirements}` : '写通知'
        } else if (templateType === 'regulation') {
          userDisplayContent = quickRequirements ? `写规章制度：${quickRequirements}` : '写规章制度'
        } else if (templateType === 'speech') {
          userDisplayContent = quickRequirements ? `写讲话稿：${quickRequirements}` : '写讲话稿'
        } else {
          userDisplayContent = quickRequirements ? `写文章：${quickRequirements}` : '写文章'
        }
      } else if (writingMode === 'reference') {
        const uploadDoc = referenceDocuments.find(d => d.type === 'upload')
        if (uploadDoc) {
          const typeLabels = {
            reply: '根据上传文件生成回函',
            imitate: '仿照上传文件风格写新公文',
            general: '基于上传文件内容生成公文'
          }
          userDisplayContent = `${typeLabels[referenceWriteType] || '参考写作'}`
          if (referenceRequirements.trim()) {
            userDisplayContent += `（要求：${referenceRequirements.trim()}）`
          }
        }
      }

      // 保存用户消息到聊天历史
      const newChatHistory = [{
        role: 'user',
        content: userDisplayContent
      }]
      setCurrentChatHistory(newChatHistory)
      writeApi.saveContent(currentSession.id, userDisplayContent, writingMode === 'quick' ? 'quick' : 'reference', 'chat', 'user').catch(() => {})

      if (writingMode === 'quick') {
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), 120000)

        console.time('[perf] 快速写作 - 总耗时')
        console.time('[perf] 快速写作 - TTFB (首 chunk)')

        const response = await fetch('/api/write/quick', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify({
            session_id: currentSession.id,
            mode: 'quick',
            style: templateType || 'general',
            user_requirements: quickRequirements || '',
            reference_content: '',
            reference_filename: '',
            rag_content: '',
            rag_references: [],
            quotes: [],
            article_content: '',
            extracted_fields: {},
            model_type: 'general',
            llm_model: 'qwen'
          })
        })
        clearTimeout(timeoutId)

        if (response.body && response.body.getReader) {
          const reader = response.body.getReader()
          const decoder = new TextDecoder('utf-8')
          let buffer = ''
          let output = ''
          let hasFirstChunk = false

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
                    // 检查是否 finish 信号
                    if (data.finish) continue
                    if (data.content) {
                      if (!hasFirstChunk) {
                        hasFirstChunk = true
                        console.timeEnd('[perf] 快速写作 - TTFB (首 chunk)')
                      }
                      output += data.content
                      // 增量渲染：每收到一个 chunk 都更新编辑器内容
                      const articleMatch = output.match(/---ARTICLE---\n?([\s\S]*?)(?=---SUMMARY---|$)/)
                      const partialContent = articleMatch ? articleMatch[1].trim() : output
                      setCurrentSessionOutput(partialContent)
                    }
                  }
                } catch (e) {
                  console.error('Parse error:', e)
                }
              }
            }
          }

          console.timeEnd('[perf] 快速写作 - 总耗时')

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
            setCurrentChatHistory(updatedChatHistory)
            await writeApi.saveContent(currentSession.id, summaryContent, 'quick', 'chat', 'assistant')

            setCurrentSessionOutput(articleContent)
          }
        }

        // 切换到内容页面
        setCurrentPage('content')
        localStorage.setItem('currentPage', 'content')

      } else if (writingMode === 'reference') {
        // 参考写作：调用 /api/generate/reference-write
        const uploadDoc = referenceDocuments.find(d => d.type === 'upload')
        if (!uploadDoc) return

        // 需要先上传文件获取内容
        const fileData = await uploadFileToSession(uploadDoc.file)

        // 如果后端没有解析出内容，尝试本地读取
        let refContent = fileData?.parsed_content || ''
        if (!refContent && uploadDoc.file) {
          // PDF 文件不适合 readAsText，只对 md/txt 做本地 fallback
          const ext = uploadDoc.file.name?.split('.').pop()?.toLowerCase()
          if (ext === 'md' || ext === 'txt') {
            refContent = await readFileAsText(uploadDoc.file)
          }
        }

        const response = await fetch('/api/generate/reference-write', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: currentSession.id,
            reference_content: refContent,
            reference_filename: uploadDoc.filename || '',
            generate_type: referenceWriteType,
            topic: referenceRequirements.trim() || uploadDoc.filename || '',
            requirements: referenceRequirements.trim() || '',
            model_name: DEFAULT_MODEL,
            use_knowledge_base: false,
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
        const typeLabels = {
          reply: '生成回函',
          imitate: '仿写公文',
          general: '基于内容生成'
        }
        let summaryContent = (typeLabels[referenceWriteType] || '参考写作') + '完成'

        const articleMatch = fullContent.match(/---ARTICLE---\n?([\s\S]*?)(?:---SUMMARY---|$)/)
        const summaryMatch = fullContent.match(/---SUMMARY---\n?([\s\S]*?)$/)

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
        setCurrentChatHistory(updatedChatHistory)
        await writeApi.saveContent(currentSession.id, summaryContent, 'reference', 'chat', 'assistant')

        setCurrentSessionOutput(articleContent)
        setCurrentPage('content')
        localStorage.setItem('currentPage', 'content')
      }
    } catch (error) {
      console.error('生成失败:', error)
      alert('生成失败: ' + (error.message || '未知错误'))
    } finally {
      setIsGenerating(false)
    }
  }

  // 上传文件辅助函数
  const uploadFileToSession = async (file) => {
    if (!file || !currentSession) return null
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('auto_parse', 'true')
      formData.append('auto_extract', 'false')

      const response = await fetch(`/api/upload/session/${currentSession.id}`, {
        method: 'POST',
        body: formData
      })
      const result = await response.json()
      if (result.code === 200 && result.data) {
        return result.data
      }
      return null
    } catch (error) {
      console.error('文件上传失败:', error)
      return null
    }
  }

  // 读取本地文件内容作为 fallback
  const readFileAsText = (file) => {
    return new Promise((resolve) => {
      if (!file) return resolve('')
      const reader = new FileReader()
      reader.onload = (e) => resolve(e.target.result)
      reader.onerror = () => resolve('')
      reader.readAsText(file)
    })
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
          currentPage === 'start' ? (
            <StartPage
              currentSession={currentSession}
              onGenerate={handleStartGeneration}
              isGenerating={isGenerating}
            />
          ) : (
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
          )
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