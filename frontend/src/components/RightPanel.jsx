import { useState } from 'react'

function RightPanel({ activeModule, onModuleChange, stepParams, onStepParamsChange, polishParams, onPolishParamsChange, currentSession }) {
  // 如果没有当前会话，不显示内容
  if (!currentSession) {
    return null
  }

  // 步骤写作参数处理
  const handleStepParamChange = (field, value) => {
    onStepParamsChange(prev => ({
      ...prev,
      [field]: value
    }))
  }
  
  // 校对润色参数处理
  const handlePolishParamChange = (field, value) => {
    onPolishParamsChange(prev => ({
      ...prev,
      [field]: value
    }))
  }

  return (
    <div className="right-panel">
      <div className="module-switch">
        <div className="module-title">功能切换面板</div>
        <div className="module-options">
          <div 
            className={`module-option ${activeModule === 'quick' ? 'active' : ''}`}
            onClick={() => onModuleChange('quick')}
          >
            <input 
              type="radio" 
              name="module" 
              value="quick" 
              checked={activeModule === 'quick'} 
              onChange={() => onModuleChange('quick')}
            />
            <label>快速写作</label>
          </div>
          <div 
            className={`module-option ${activeModule === 'step' ? 'active' : ''}`}
            onClick={() => onModuleChange('step')}
          >
            <input 
              type="radio" 
              name="module" 
              value="step" 
              checked={activeModule === 'step'} 
              onChange={() => onModuleChange('step')}
            />
            <label>步骤写作</label>
          </div>
          <div 
            className={`module-option ${activeModule === 'polish' ? 'active' : ''}`}
            onClick={() => onModuleChange('polish')}
          >
            <input 
              type="radio" 
              name="module" 
              value="polish" 
              checked={activeModule === 'polish'} 
              onChange={() => onModuleChange('polish')}
            />
            <label>校对润色</label>
          </div>
        </div>
      </div>

      <div className="feature-panel">
        {/* 快速写作功能面板 */}
        {activeModule === 'quick' && (
          <div className="feature-section">
            <div className="feature-section">
              <h3>模型类型:</h3>
              <div className="radio-group">
                <div className="radio-item">
                  <input 
                    type="radio" 
                    name="model-quick" 
                    value="general" 
                    checked={true}
                    onChange={() => {}} 
                  />
                  <label>通用</label>
                </div>
                <div className="radio-item">
                  <input 
                    type="radio" 
                    name="model-quick" 
                    value="creative" 
                    onChange={() => {}} 
                  />
                  <label>创意</label>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 步骤写作功能面板 */}
        {activeModule === 'step' && (
          <div className="feature-section">
       
            <div className="feature-section">
              <h3>产品名称:</h3>
              <input 
                type="text" 
                placeholder="请输入产品名称" 
                value={stepParams.productName}
                onChange={(e) => handleStepParamChange('productName', e.target.value)}
              />
            </div>
            <div className="feature-section">
              <h3>卖点:</h3>
              <input 
                type="text" 
                placeholder="请输入产品卖点（逗号分隔）" 
                value={stepParams.sellingPoints}
                onChange={(e) => handleStepParamChange('sellingPoints', e.target.value)}
              />
            </div>
            <div className="feature-section">
              <h3>风格:</h3>
              <select 
                value={stepParams.style}
                onChange={(e) => handleStepParamChange('style', e.target.value)}
              >
                <option value="simple">简洁</option>
                <option value="vivid">生动</option>
                <option value="formal">正式</option>
              </select>
            </div>
            <div className="feature-section">
              <h3>长度:</h3>
              <div className="radio-group">
                <div className="radio-item">
                  <input 
                    type="radio" 
                    name="length" 
                    value="short" 
                    checked={stepParams.length === 'short'}
                    onChange={() => handleStepParamChange('length', 'short')} 
                  />
                  <label>短</label>
                </div>
                <div className="radio-item">
                  <input 
                    type="radio" 
                    name="length" 
                    value="medium" 
                    checked={stepParams.length === 'medium'}
                    onChange={() => handleStepParamChange('length', 'medium')} 
                  />
                  <label>中</label>
                </div>
                <div className="radio-item">
                  <input 
                    type="radio" 
                    name="length" 
                    value="long" 
                    checked={stepParams.length === 'long'}
                    onChange={() => handleStepParamChange('length', 'long')} 
                  />
                  <label>长</label>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 校对润色功能面板 */}
        {activeModule === 'polish' && (
          <div className="feature-section">
           
            <div className="feature-section">
              <h3>润色类型:</h3>
              <div className="radio-group">
                <div className="radio-item">
                  <input 
                    type="radio" 
                    name="polish-type" 
                    value="check" 
                    checked={polishParams.polishType === 'check'}
                    onChange={() => handlePolishParamChange('polishType', 'check')} 
                  />
                  <label>检查</label>
                </div>
                <div className="radio-item">
                  <input 
                    type="radio" 
                    name="polish-type" 
                    value="optimize" 
                    checked={polishParams.polishType === 'optimize'}
                    onChange={() => handlePolishParamChange('polishType', 'optimize')} 
                  />
                  <label>优化</label>
                </div>
                <div className="radio-item">
                  <input 
                    type="radio" 
                    name="polish-type" 
                    value="expand" 
                    checked={polishParams.polishType === 'expand'}
                    onChange={() => handlePolishParamChange('polishType', 'expand')} 
                  />
                  <label>扩写</label>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="feature-section">
          <button className="generate-btn" style={{ width: '100%' }}>
            生成
          </button>
        </div>
      </div>
    </div>
  )
}

export default RightPanel