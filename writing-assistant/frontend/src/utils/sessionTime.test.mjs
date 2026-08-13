import assert from 'node:assert/strict'
import test from 'node:test'

import { formatSessionTime } from './sessionTime.js'

test('formats SQLite UTC timestamps as Beijing time', () => {
  assert.equal(
    formatSessionTime('2026-07-23 11:52:33'),
    '2026-07-23 19:52:33',
  )
})

test('does not shift timestamps that already include a timezone twice', () => {
  assert.equal(
    formatSessionTime('2026-07-23T19:52:33+08:00'),
    '2026-07-23 19:52:33',
  )
})

test('keeps an unknown timestamp visible instead of hiding it', () => {
  assert.equal(formatSessionTime('unknown'), 'unknown')
})
