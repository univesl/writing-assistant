import test from 'node:test'
import assert from 'node:assert/strict'

import { parseSseFrame } from './agentRunStream.js'

test('parses public SSE event and cursor', () => {
  const parsed = parseSseFrame('id: 7\nevent: warning\ndata: {"id":7,"type":"warning","data":{"message":"注意"}}')
  assert.equal(parsed.id, 7)
  assert.equal(parsed.event, 'warning')
  assert.equal(parsed.data.data.message, '注意')
})

test('ignores heartbeat-only frames and supports multiline data', () => {
  assert.equal(parseSseFrame(': heartbeat'), null)
  const parsed = parseSseFrame('id: 8\ndata: {"id":8,\ndata: "type":"run.completed"}')
  assert.equal(parsed.data.type, 'run.completed')
})
