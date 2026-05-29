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
    let prompt = ''
    
    const articleContent = getArticleContent()
    const isEditRequest = articleContent && quickRequirements && quickRequirements.trim()
    
    if (isEditRequest) {
      const styleName = templateType === 'notice' ? '通知' : 
                        templateType === 'regulation' ? '规章制度' : 
                        templateType === 'speech' ? '讲话稿' : '正式文章'
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
      if (isEditRequest) {
        const styleName = templateType === 'notice' ? '通知' : 
                          templateType === 'regulation' ? '规章制度' : 
                          templateType === 'speech' ? '讲话稿' : '正式文章'
        
        prompt = `现有文章内容：
${articleContent}

用户要求：${quickRequirements}

请根据用户要求修改或扩展上述文章。如果用户的要求与现有文章无关（比如要求写一个完全不同的新文章），请告知用户需要创建新会话来写新文章。

【文体类型】${styleName}
【风格要求】请参照北航真实公文风格：语言正式、严谨、规范。修改后的文章应符合${styleName}的写作规范，保持整体风格统一、逻辑严谨。

请严格按照以下格式输出内容：

---ARTICLE---
[这里是修改后的完整文章内容，使用Markdown格式。标题用#开头，各级标题用相应数量的#，正文直接书写]

---SUMMARY---
[这里是对修改内容的简要说明，说明主要做了哪些修改，不超过100字]`
      } else {
        // 生成新文章时，先调用知识库生成 API
        let knowledgeBaseContent = ''
        let knowledgeBaseReferences = []
        
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
            knowledgeBaseContent = generateResult.content
            knowledgeBaseReferences = generateResult.references || []
            console.log('知识库生成成功，参考文献:', knowledgeBaseReferences)
          }
        } catch (error) {
          console.error('知识库生成失败:', error)
        }
        
        const getStylePrompt = (type, requirements, ragContent, ragRefs, refDocs, quoteList) => {
          // 基础信息
          const baseInfo = requirements || '未提供具体要求'
          
          // RAG参考信息
          let ragSection = ''
          if (ragContent) {
            const typeName = type === 'notice' ? '通知' : type === 'regulation' ? '规章制度' : type === 'speech' ? '讲话稿' : '公文'
            ragSection = `\n\n【北航真实公文原文参考】\n以下是从北航公文知识库检索到的真实公文原文，请作为本次撰写的核心参考，重点学习其格式结构、用语习惯和行文风格：\n\n${ragContent}`
            ragSection += `\n\n【重要提示】如果上述参考公文的文体与本次要写的"${typeName}"不同，请只参考其语言风格和公文用语习惯，不要照搬其内容结构。本次需要严格按照"${typeName}"的规范格式来组织文章。`
            if (ragRefs && ragRefs.length > 0) {
              ragSection += `\n\n参考来源：${ragRefs.join('、')}`
            }
          }
          
          // 参考文档
          let docSection = ''
          if (refDocs && refDocs.length > 0) {
            docSection = `\n\n【参考文档】\n以下文档供内容参考（提取关键信息，不要照搬）：\n`
            refDocs.forEach((doc, index) => {
              const docLabel = doc.type === 'upload' ? '上传参考' : '知识库参考'
              docSection += `\n[${docLabel} ${index + 1}: ${doc.filename}]\n${doc.content.substring(0, 4000)}${doc.content.length > 4000 ? '...' : ''}\n`
            })
          }
          
          // 引用内容
          let quoteSection = ''
          if (quoteList && quoteList.length > 0) {
            quoteSection = `\n\n【引用内容】\n以下内容需融入文章（适当引用，灵活处理）：\n`
            quoteList.forEach((quote, index) => {
              quoteSection += `\n引用${index + 1}：${quote.text}\n`
            })
          }
          
          // 根据不同文体返回不同提示词
          if (type === 'notice') {
            return `你是一位专业的公文写作专家。请参照北航真实公文风格：语言正式、严谨、规范，撰写一篇【通知】公文。

【核心要求】（以用户要求为主线）
${baseInfo}

【通知公文写作规范】
1. 标题格式：严格按照"关于XXX的通知"格式，如"北京航空航天大学关于召开2025年教学工作会议的通知"。标题居中，不加书名号，不加标点。
2. 正文结构：
   - 开头称谓：顶格写称呼（如"各单位："、"各位老师："），后用冒号
   - 开头：交代发文缘由、目的或依据（常用"为了……"、"根据……"、"按照……"等句式）
   - 主体：分条叙述，使用"一、"、"二、"、"三、"编号。每条内容明确具体，涉及时间、地点、人员等关键信息必须精确
   - 结尾：使用"特此通知。"收束全文
3. 落款：发文单位名称（居右）、发文日期（居右，用中文数字"二〇二五年X月X日"格式）
4. 语言特点：简洁明了、准确规范、指令性强。使用"应"、"须"、"请"、"不得"等公文常用词
5. 段落格式：段首空两格，层次分明${ragSection}${docSection}${quoteSection}

【写作原则】
- 严格以用户提供的核心要求为主线，不得偏离主题
- 参考知识库的格式和风格，但不要照搬其内容
- 时间、地点、人员等关键信息必须明确具体
- 建议控制在500-800字，根据实际需要调整，避免冗长
- 模仿北航公文严谨风格：多用陈述句，少用感叹句；用语规范，避免口语化

请按照以下格式输出：

---ARTICLE---
[通知正文，使用Markdown格式]

---SUMMARY---
[100字以内总结]`
          } else if (type === 'regulation') {
            return `你是一位专业的公文写作专家。请参照北航真实公文风格：语言正式、严谨、规范，撰写一篇【规章制度】。

【核心要求】（以用户要求为主线）
${baseInfo}

【规章制度写作规范】
1. 标题格式：直接使用规章制度名称（如"实验室安全管理制度"），不冠以发文单位
2. 正文结构（采用标准章条款结构）：
   - 第一章 总则：说明制定目的（"为/为了……"）、适用范围（"本办法适用于……"）、基本原则
   - 第X章 具体章节：按内容逻辑分章，每章下设若干条款。章节命名规范，如"第二章 组织机构与职责"
   - 最后一章 附则：说明解释权归属、生效日期（"本办法自发布之日起施行"）
3. 条款格式规范：
   - 使用"第X条"连续编号，从头至尾不中断
   - 一条一义，每条只规定一个事项
   - 必要时使用"（一）（二）（三）"分款，分款内使用"1. 2. 3."进一步细分
   - 引用其他条款时使用"本制度第X条"
4. 语言特点：严谨规范、权责明确、可操作性强。使用"应当"、"不得"、"须"、"方可"等法规范用语
5. 行文要求：条理清晰、相互衔接、逻辑严密，避免重复和矛盾${ragSection}${docSection}${quoteSection}

【写作原则】
- 严格以用户提供的核心要求为主线构建条款
- 参考知识库的条款结构和表述方式，但不要照搬内容
- 权利义务必须对等，逻辑严密
- 建议控制在800-1500字，根据实际需要调整，条款清晰完整
- 参照北航规章制度风格：用语规范、结构严谨、层次分明

请按照以下格式输出：

---ARTICLE---
[规章制度正文，使用Markdown格式]

---SUMMARY---
[100字以内总结]`
          } else if (type === 'speech') {
            return `你是一位专业的讲话稿撰稿人。请参照北航真实公文风格：语言正式、严谨、规范，撰写一篇【讲话稿】。

【核心要求】（以用户要求为主线）
${baseInfo}

【讲话稿写作规范】
1. 标题：简洁有力，点明主题。可使用"在XXX会议上的讲话"或"凝心聚力 开拓创新——在XXX会议上的讲话"等格式
2. 开场问候：
   - 顶格写称呼，如"尊敬的各位领导、各位老师："、"各位来宾、各位同事："
   - 称呼后用冒号
   - 另起一段写开场语（"大家好！"、"上午好！"等）
   - 致谢或引入正题
3. 正文结构（层次递进）：
   - 第一部分：肯定成绩/说明背景/指出意义（"过去一年……"、"当前……"）
   - 第二部分：分析形势/指出问题/提出要求（"但同时我们也应看到……"）
   - 第三部分：部署工作/明确方向/发出号召（"下一步，我们要……"）
   - 各部分之间使用"一、"、"二、"、"三、"或"首先"、"其次"、"再次"过渡
4. 结尾：
   - 总结要点，升华主题
   - 发出号召或提出希望（"让我们……"）
   - 致谢收束（"谢谢大家！"）
5. 语言特点：
   - 口语化与书面化结合，适合朗读
   - 长短句结合，节奏感强
   - 适当使用排比、对仗、设问等修辞手法增强感染力
   - 情感真挚，接地气，避免空洞套话
   - 多用"我们"增强认同感${ragSection}${docSection}${quoteSection}

【写作原则】
- 严格以用户提供的核心要求为主线组织内容
- 参考知识库的讲话风格，但不要照搬其内容
- 要有现场感，听众能听得进去
- 建议控制在800-1500字，根据实际需要调整，适合8-15分钟演讲
- 参照北航讲话稿风格：内容务实、语言精炼、层次分明、有号召力

请按照以下格式输出：

---ARTICLE---
[讲话稿正文，使用Markdown格式]

---SUMMARY---
[100字以内总结]`
          } else {
            // 通用文章
            return `你是一位专业的公文写作专家。请参照北航真实公文风格：语言正式、严谨、规范，撰写一篇正式文章。

【核心要求】
${baseInfo}

【正式公文写作规范】
1. 标题：简洁明确，概括全文主旨
2. 正文结构：
   - 开头：说明背景、目的或依据，开门见山
   - 主体：条理清晰，逻辑严密，分层次阐述
   - 结尾：总结全文，或提出要求、展望
3. 语言要求：
   - 用语正式、严谨、规范
   - 用词准确，避免歧义
   - 句式完整，避免口语化表达
   - 适当使用公文惯用语（"现将……如下"、"特此……"等）
4. 段落格式：层次分明，段落衔接自然
5. 落款：发文单位名称（居右）、发文日期（居右，用中文数字"二〇二五年X月X日"格式）
6. 行文风格：客观中立，实事求是，不夸张不渲染${ragSection}${docSection}${quoteSection}

【写作原则】
- 严格以用户提供的核心要求为主线，不得偏离主题
- 参考知识库的格式和风格，但不要照搬其内容
- 建议控制在600-1000字，根据实际需要调整
- 参照北航正式公文风格：逻辑严谨、用语规范、结构完整

请按照以下格式输出：

---ARTICLE---
[文章内容，使用Markdown格式]

---SUMMARY---
[100字以内总结]`
          }
        }
        
        // 构建完整提示词
        prompt = getStylePrompt(
          templateType,
          quickRequirements,
          knowledgeBaseContent,
          knowledgeBaseReferences,
          referenceDocuments,
          quotes
        )
      }
      
      const url = '/api/write/quick'
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          session_id: currentSession.id,
          prompt: prompt,
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
      let prompt
      let userDisplayContent
      
      if (hasQuotes) {
        prompt = `你是一个专业的文字编辑助手。用户需要修改文章中的部分内容。

原始文章内容：
${articleContent}

用户选中的需要修改的内容：
${originalQuotes.map((q, i) => `--- 引用 ${i + 1} ---\n${q}`).join('\n')}

用户的修改要求：${chatInput}

请根据用户的修改要求，对选中内容进行修改，并输出完整的修改后文章。
注意：只修改用户选中的部分，保持文章其余部分不变。
【风格要求】请保持北航公文的正式风格：语言严谨、准确、简练，保持客观中立的官方口吻。

请严格按照以下格式输出：

---ARTICLE---
[这里是修改后的完整文章内容，使用Markdown格式]

---SUMMARY---
[简要说明做了什么修改，不超过50字]`
        userDisplayContent = chatInput
      } else {
        prompt = `现有文章内容：
${articleContent}

用户要求：${chatInput}

请根据用户要求修改或扩展上述文章。
【风格要求】请保持北航公文的正式风格：语言严谨、准确、简练，保持客观中立的官方口吻。

请严格按照以下格式输出内容：

---ARTICLE---
[这里是修改后的完整文章内容，使用Markdown格式。标题用#开头，各级标题用相应数量的#，正文直接书写]

---SUMMARY---
[这里是对修改内容的简要说明，说明主要做了哪些修改，不超过100字]`
        userDisplayContent = chatInput
      }
      
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
          prompt: prompt,
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
