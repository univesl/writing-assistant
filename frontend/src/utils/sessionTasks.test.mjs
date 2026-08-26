import assert from 'node:assert/strict'
import test from 'node:test'

import {
  finishSessionTask,
  getSessionTask,
  startSessionTask,
} from './sessionTasks.js'

test('different sessions can run while the same session is rejected', () => {
  const first = startSessionTask({}, 101, { operationId: 'a', kind: 'generate' })
  const second = startSessionTask(first.tasks, 202, { operationId: 'b', kind: 'generate' })

  assert.equal(startSessionTask(second.tasks, 101, { operationId: 'c' }), null)
  assert.equal(getSessionTask(second.tasks, 101).operationId, 'a')
  assert.equal(getSessionTask(second.tasks, 202).operationId, 'b')
})

test('finishing one session does not clear another session task', () => {
  const first = startSessionTask({}, 101, { operationId: 'a' })
  const second = startSessionTask(first.tasks, 202, { operationId: 'b' })
  const remaining = finishSessionTask(second.tasks, 101, 'a')

  assert.equal(getSessionTask(remaining, 101), null)
  assert.equal(getSessionTask(remaining, 202).operationId, 'b')
})
