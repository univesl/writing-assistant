import React, { useState, useEffect } from 'react'
import { writeApi } from '../api/writeApi'

function MainContent({ activeModule, currentSession, stepParams, polishParams, currentOutput, onContentUpdate }) {
  const [inputText, setInputText] = useState('')
  const [outputText, setOutputText] = useState(currentOutput || '')
  const [isGenerating, setIsGenerating] = useState(false)
  const [modelType, setModelType] = useState('general')
  
  // 监听currentOutput变化，当会话切换时更新内容
  useEffect(() => {
    setOutputText(currentOutput || '')
  }, [currentOutput])

  const handleGenerate = async () => {
    if (!inputText.trim() || !currentSession) return
    
    console.log('用户点击生成按钮')
    console.log('当前活动模块:', activeModule)
    console.log('用户输入内容:', inputText)
    console.log('当前会话ID:', currentSession.id)
    
    setIsGenerating(true)
    setOutputText('生成中...')
    
    try {
      let result
      switch (activeModule) {
        case 'quick':
          // 直接使用fetch API测试SSE响应
          const url = 'http://127.0.0.1:8000/api/write/quick'
          const response = await fetch(url, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              session_id: currentSession.id,
              prompt: inputText,
              model_type: modelType
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
              
              result = { content: output }
              console.log('Final result:', result)
            } catch (e) {
              console.error('Stream reading error:', e)
              setOutputText('读取响应失败，请重试...')
            }
          } else {
            // 非流式处理
            const data = await response.json()
            console.log('Non-stream data:', data)
            setOutputText(data.content || 'No content')
            result = data
          }
          break
          
        case 'step':
          // 将卖点字符串转换为数组
          const sellingPointsArray = stepParams.sellingPoints
            ? stepParams.sellingPoints.split(',').map(sp => sp.trim()).filter(sp => sp)
            : []
          
          // 直接使用fetch API处理SSE响应
          const stepUrl = 'http://127.0.0.1:8000/api/write/step'
          const stepResponse = await fetch(stepUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              session_id: currentSession.id,
              product_name: stepParams.productName,
              selling_points: sellingPointsArray, // 后端需要数组格式
              style: stepParams.style,
              length: stepParams.length
            })
          })
          
          console.log('Step write fetch response:', stepResponse)
          console.log('Step response type:', stepResponse.type)
          console.log('Step is readable:', stepResponse.body?.readable)
          
          let stepOutput = ''
          
          if (stepResponse.body && stepResponse.body.getReader) {
            const stepReader = stepResponse.body.pipeThrough(new TextDecoderStream()).getReader()
            
            while (true) {
              const { done, value } = await stepReader.read()
              console.log('Step stream chunk:', { done, value })
              if (done) break
              
              const lines = value.split('\n')
              for (const line of lines) {
                if (line.startsWith('data:')) {
                  try {
                    const dataStr = line.slice(5).trim()
                    if (dataStr) {
                        const data = JSON.parse(dataStr)
                        console.log('Step parsed data:', data)
                        stepOutput += data.content
                        setOutputText(stepOutput)
                        // 更新会话内容到全局状态
                        if (onContentUpdate) {
                          onContentUpdate(currentSession.id, stepOutput)
                        }
                        console.log('Step output updated:', stepOutput)
                      }
                  } catch (e) {
                    console.error('Step parse error:', e)
                  }
                }
              }
            }
            
            result = { content: stepOutput }
          } else {
            // 非流式处理
            const data = await stepResponse.json()
            console.log('Step non-stream data:', data)
            setOutputText(data.content || 'No content')
            result = data
          }
          break
          
        case 'polish':
          // 直接使用fetch API处理SSE响应
          const polishUrl = 'http://127.0.0.1:8000/api/write/polish'
          const polishResponse = await fetch(polishUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              session_id: currentSession.id,
              content: inputText,
              polish_type: polishParams.polishType
            })
          })
          
          console.log('Polish fetch response:', polishResponse)
          console.log('Polish response type:', polishResponse.type)
          console.log('Polish is readable:', polishResponse.body?.readable)
          
          let polishOutput = ''
          
          if (polishResponse.body && polishResponse.body.getReader) {
            const polishReader = polishResponse.body.pipeThrough(new TextDecoderStream()).getReader()
            
            while (true) {
              const { done, value } = await polishReader.read()
              console.log('Polish stream chunk:', { done, value })
              if (done) break
              
              const lines = value.split('\n')
              for (const line of lines) {
                if (line.startsWith('data:')) {
                  try {
                    const dataStr = line.slice(5).trim()
                    if (dataStr) {
                        const data = JSON.parse(dataStr)
                        console.log('Polish parsed data:', data)
                        polishOutput += data.content
                        setOutputText(polishOutput)
                        // 更新会话内容到全局状态
                        if (onContentUpdate) {
                          onContentUpdate(currentSession.id, polishOutput)
                        }
                        console.log('Polish output updated:', polishOutput)
                      }
                  } catch (e) {
                    console.error('Polish parse error:', e)
                  }
                }
              }
            }
            
            result = { content: polishOutput }
          } else {
            // 非流式处理
            const data = await polishResponse.json()
            console.log('Polish non-stream data:', data)
            setOutputText(data.content || 'No content')
            result = data
          }
          break
          
        default:
          break
      }
      
      // 保存生成的内容
      if (result && result.content) {
        await writeApi.saveContent(currentSession.id, result.content, activeModule)
      }
    } catch (error) {
      console.error('生成失败:', error)
      setOutputText('生成失败，请重试...')
    } finally {
      setIsGenerating(false)
    }
  }

  const handleClear = () => {
    setInputText('')
    setOutputText('')
  }

  const handleCopy = () => {
    if (outputText) {
      navigator.clipboard.writeText(outputText)
        .then(() => alert('复制成功'))
        .catch(err => console.error('复制失败:', err))
    }
  }

  // 如果没有当前会话，不显示内容
  if (!currentSession) {
    return null
  }

  return (
    <div className="main-content">
      <div className="module-title">
        {{
          quick: '快速写作',
          step: '步骤式写作',
          polish: '校对润色'
        }[activeModule]}
      </div>
      
      <div className="input-area">
        <textarea
          placeholder={{
            quick: '请输入写作需求...',
            step: '请输入产品信息和需求...',
            polish: '请输入需要校对润色的文本...'
          }[activeModule]}
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          disabled={isGenerating}
        />
      </div>
      
      <div className="control-bar">
        <select
          className="model-selector"
          value={modelType}
          onChange={(e) => setModelType(e.target.value)}
          disabled={isGenerating}
        >
          <option value="general">通用</option>
          <option value="creative">创意</option>
        </select>
        
        <button
          className="generate-btn"
          onClick={handleGenerate}
          disabled={isGenerating || !inputText.trim()}
        >
          {isGenerating ? '生成中...' : '生成'}
        </button>
      </div>
      
      <div className="output-area">
        {outputText || '生成的内容将显示在这里...'}
      </div>
      
      <div className="action-bar">
        <button className="action-btn" onClick={handleClear} disabled={isGenerating}>
          清空
        </button>
        <button className="action-btn" onClick={handleCopy} disabled={!outputText}>
          复制全文
        </button>
      </div>
    </div>
  )
}

export default MainContent