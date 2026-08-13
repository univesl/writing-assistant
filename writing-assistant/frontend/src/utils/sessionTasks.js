/**
 * 会话级任务状态的纯函数。
 *
 * App 用 ref 保存同一份状态，保证同一事件循环中两个按钮同时触发时，
 * 不会因为 React state 尚未刷新而重复启动同一会话的正文任务。
 */

export function taskKey(sessionId) {
  return sessionId === null || sessionId === undefined ? '' : String(sessionId)
}

export function startSessionTask(tasks, sessionId, task) {
  const key = taskKey(sessionId)
  if (!key || tasks[key]) return null

  const nextTask = {
    ...task,
    sessionId,
    status: 'running',
  }

  return {
    task: nextTask,
    tasks: {
      ...tasks,
      [key]: nextTask,
    },
  }
}

export function finishSessionTask(tasks, sessionId, operationId) {
  const key = taskKey(sessionId)
  const current = tasks[key]
  if (!current || (operationId && current.operationId !== operationId)) {
    return tasks
  }

  const next = { ...tasks }
  delete next[key]
  return next
}

export function getSessionTask(tasks, sessionId) {
  return tasks[taskKey(sessionId)] || null
}

export function hasSessionTask(tasks, sessionId) {
  return Boolean(getSessionTask(tasks, sessionId))
}
