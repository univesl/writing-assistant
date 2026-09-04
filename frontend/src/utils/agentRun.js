export const ACTIVE_AGENT_STATUSES = new Set(['queued', 'running'])
export const RETRYABLE_AGENT_STATUSES = new Set(['failed', 'cancelled', 'interrupted'])
export const EDITOR_STREAM_TASK_TYPES = new Set(['quick', 'draft', 'reference', 'reply', 'imitate'])

export function isActiveAgentRun(run) {
  return ACTIVE_AGENT_STATUSES.has(run?.status)
}

export function isRetryableAgentRun(run) {
  return RETRYABLE_AGENT_STATUSES.has(run?.status)
}

export function canStreamArticleToEditor(run) {
  return EDITOR_STREAM_TASK_TYPES.has(run?.task_type) && Number(run?.base_version || 0) === 0
}

export function shouldApplyRunArticleToEditor(run) {
  return run?.outcome !== 'proposal' && Boolean(run?.final_article)
}

export function completeAgentRun(run, data = {}) {
  const article = data.article || data.final_article || run.final_article || ''
  return {
    ...run,
    status: 'completed',
    current_stage: 'finalize',
    final_article: article,
    article_snapshot: article || run.article_snapshot,
    summary: data.summary || run.summary,
    references: data.references || run.references || [],
    warnings: data.warnings || run.warnings || [],
    issues: data.issues || run.issues || [],
    outcome: data.outcome || run.outcome || 'document',
    applied_version: data.applied_version ?? run.applied_version,
    activated_skills: data.activated_skills || run.activated_skills || [],
    workflow_plan: data.workflow_plan || run.workflow_plan || {},
  }
}
