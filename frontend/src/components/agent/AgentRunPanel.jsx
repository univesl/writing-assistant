import { formatReferenceLabel } from '../../utils/generatedOutput'
import { isActiveAgentRun, isRetryableAgentRun } from '../../utils/agentRun'

const STAGE_LABELS = {
  prepare: '校验请求',
  material_analysis: '逐份分析参考材料',
  reference_strategy: '规划材料用途',
  skill: '加载 Skill',
  planning: '分析写作要求',
  retrieval_plan: '规划知识库检索',
  retrieval: '执行资料检索',
  evidence_filter: '筛选检索证据',
  outline: '生成提纲',
  draft: '起草正文',
  material_review: '审查材料使用',
  validation: '校验正文',
  revision: '定向修订',
  finalize: '整理结果',
}

const STATUS_LABELS = {
  queued: '排队中', running: '运行中', completed: '已完成', failed: '失败',
  cancelled: '已取消', interrupted: '已中断',
}

const REFERENCE_MODE_LABELS = {
  reply: '生成回函',
  base_tuning: '底稿微调',
  synthesize: '智能参考写作',
}

function eventLabel(event) {
  if (event.type === 'stage.started') return `开始：${STAGE_LABELS[event.stage] || event.stage}`
  if (event.type === 'stage.completed') {
    const duration = event.data?.duration_ms ? ` · ${(event.data.duration_ms / 1000).toFixed(1)} 秒` : ''
    return `完成：${STAGE_LABELS[event.stage] || event.stage}${duration}`
  }
  if (event.type === 'source.added') {
    if (event.data?.reference?.kind === 'uploaded_file') return '已采用一份上传材料'
    if (event.data?.reference?.kind === 'web_result') return '已加入一条互联网来源'
    return '已加入一条检索来源'
  }
  if (event.type === 'material.plan.ready') return '已形成材料使用方案'
  if (event.type === 'warning') return event.data?.message || '需要注意'
  if (event.type === 'run.started') return `Agent 已启动（第 ${event.data?.attempt || 1} 次）`
  if (event.type === 'run.completed') return '正文生成完成'
  if (event.type === 'run.cancelled') return '运行已取消'
  if (event.type === 'run.failed') return event.data?.message || '运行失败'
  return null
}

export default function AgentRunPanel({ run, events = [], onCancel, onRetry }) {
  if (!run) {
    return <div className="agent-empty">本会话还没有 Agent 运行记录。</div>
  }
  const hiddenEvents = new Set(['content.delta', 'skill.activated', 'plan.ready'])
  const visibleEvents = events.filter(event => !hiddenEvents.has(event.type))
  const active = isActiveAgentRun(run)
  const retryable = isRetryableAgentRun(run)
  const isProposal = run.outcome === 'proposal'
  const materialPlan = run.workflow_plan?.material_plan
  const sourceLabels = [...new Set((run.references || [])
    .map((item, index) => formatReferenceLabel(
      typeof item === 'string'
        ? item
        : item.title || item.name || item.source || `来源 ${index + 1}`,
    ))
    .filter(Boolean))]

  return (
    <div className="agent-run-panel" aria-live="polite">
      <div className="agent-run-header">
        <div>
          <strong className="agent-run-status">
            <span>{isProposal ? '候选稿' : STATUS_LABELS[run.status] || run.status}</span>
          </strong>
          <span>{STAGE_LABELS[run.current_stage] || run.current_stage || '准备中'}</span>
        </div>
        {active && <button onClick={() => onCancel?.(run)} className="agent-secondary-btn">取消</button>}
        {retryable && <button onClick={() => onRetry?.(run)} className="agent-primary-btn">重试</button>}
      </div>

      <ol className="agent-timeline">
        {visibleEvents.map(event => {
          const label = eventLabel(event)
          if (!label) return null
          const tone = event.type === 'warning' || event.type === 'run.failed' ? 'warning' : 'normal'
          return <li key={event.id} className={tone}><span aria-hidden="true" /><p>{label}</p></li>
        })}
      </ol>

      {isProposal && (
        <section className="agent-result-section warning">
          <h3>未自动应用</h3>
          <p>本次结果未通过质量门，已保存为候选稿，没有覆盖当前正文。</p>
        </section>
      )}

      {!!materialPlan?.materials?.length && (
        <section className="agent-result-section">
          <h3>材料使用方案</h3>
          {materialPlan.reference_mode && (
            <p>{REFERENCE_MODE_LABELS[materialPlan.reference_mode] || materialPlan.reference_mode}</p>
          )}
          <ul>{materialPlan.materials.map(item => (
            <li key={item.file_id}>
              {item.name}：{item.roles?.join('＋') || '背景'}
              {item.priority === 'primary' ? '（重点）' : ''}
            </li>
          ))}</ul>
        </section>
      )}

      {!!sourceLabels.length && (
        <section className="agent-result-section">
          <h3>来源</h3>
          <ul>{sourceLabels.map(item => (
            <li key={item}>{item}</li>
          ))}</ul>
        </section>
      )}
      {!!run.warnings?.length && (
        <section className="agent-result-section warning">
          <h3>提醒</h3>
          <ul>{run.warnings.map((item, index) => <li key={index}>{item.message || String(item)}</li>)}</ul>
        </section>
      )}
      {!!run.issues?.length && (
        <section className="agent-result-section">
          <h3>校验问题</h3>
          <ul>{run.issues.map((item, index) => <li key={index}>{item.message || String(item)}</li>)}</ul>
        </section>
      )}
    </div>
  )
}
