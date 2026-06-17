import React, { useState, useEffect } from 'react'
import { writeApi } from '../api/writeApi'

function MainContent({ currentSession, editorContent, chatHistory, onArticleUpdate, onChatHistoryUpdate }) {
  const [isGenerating, setIsGenerating] = useState(false)
  const [chatInput, setChatInput] = useState('')

  const getArticleContent = () => {
    return editorContent || ''
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

    try {
      const userDisplayContent = chatInput

      const newChatHistory = [...(chatHistory || []), {
        role: 'user',
        content: userDisplayContent
      }]
      if (onChatHistoryUpdate) {
        onChatHistoryUpdate(currentSession.id, newChatHistory)
      }

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
                    if (data.finish) continue
                    if (data.content) {
                      output += data.content
                      // 增量渲染：实时更新编辑器内容
                      const articleMatch = output.match(/---ARTICLE---\n?([\s\S]*?)(?=---SUMMARY---|$)/)
                      const partialContent = articleMatch ? articleMatch[1].trim() : output
                      if (onArticleUpdate) {
                        onArticleUpdate(currentSession.id, partialContent)
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
            if (onChatHistoryUpdate) {
              onChatHistoryUpdate(currentSession.id, updatedChatHistory)
            }

            await writeApi.saveContent(currentSession.id, summaryContent, 'quick', 'chat', 'assistant')
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
        {(chatHistory || []).map((message, index) => (
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
                disabled={isGenerating}
                className="chat-textarea"
                placeholder="输入修改润色要求..."
                rows={3}
              />
            </div>
          </div>

          <div className="chat-actions">
            <button
              className="chat-action-btn send-btn"
              onClick={handleEditSubmit}
              disabled={isGenerating || !chatInput.trim()}
            >
              {isGenerating ? '修改中...' : '发送'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default MainContent