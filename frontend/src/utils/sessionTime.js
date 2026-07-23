const BACKEND_NAIVE_TIMESTAMP =
  /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?$/

const BEIJING_TIME_FORMATTER = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hourCycle: 'h23',
})

const parseSessionTimestamp = (value) => {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value
  }

  const text = String(value || '').trim()
  if (!text) return null

  const match = text.match(BACKEND_NAIVE_TIMESTAMP)
  if (match) {
    const [, year, month, day, hour, minute, second] = match

    // SQLite CURRENT_TIMESTAMP is UTC, while the API currently returns a
    // timezone-less string. Parse it explicitly as UTC to avoid an 8-hour
    // error when browsers otherwise assume local time.
    return new Date(Date.UTC(
      Number(year),
      Number(month) - 1,
      Number(day),
      Number(hour),
      Number(minute),
      Number(second),
    ))
  }

  const parsed = new Date(text)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

export const formatSessionTime = (value) => {
  const parsed = parseSessionTimestamp(value)
  if (!parsed) return String(value || '')

  const parts = Object.fromEntries(
    BEIJING_TIME_FORMATTER
      .formatToParts(parsed)
      .filter(({ type }) => type !== 'literal')
      .map(({ type, value: partValue }) => [type, partValue]),
  )

  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second}`
}
