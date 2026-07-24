import { useCallback, useEffect, useRef, useState } from 'react'

const DIALOG_WIDTH = 380
const DIALOG_FALLBACK_HEIGHT = 260
const DIALOG_MARGIN = 8

function AiEditDialog({
  boundaryRef,
  dialogRef,
  position,
  onPositionChange,
  request,
  onRequestChange,
  error,
  isSubmitting,
  onSubmit,
  onCancel,
}) {
  const [isDragging, setIsDragging] = useState(false)
  const dragRef = useRef(null)

  const clampPosition = useCallback((nextPosition, dialogHeight = DIALOG_FALLBACK_HEIGHT) => {
    const boundaryRect = boundaryRef.current?.getBoundingClientRect()
    if (!boundaryRect) return nextPosition

    const minX = boundaryRect.left + DIALOG_MARGIN
    const maxX = boundaryRect.right - DIALOG_WIDTH - DIALOG_MARGIN
    const minY = boundaryRect.top + DIALOG_MARGIN
    const maxY = boundaryRect.bottom - dialogHeight - DIALOG_MARGIN

    return {
      x: Math.min(Math.max(nextPosition.x, minX), Math.max(minX, maxX)),
      y: Math.min(Math.max(nextPosition.y, minY), Math.max(minY, maxY)),
    }
  }, [boundaryRef])

  const startDrag = useCallback((e) => {
    if (!dialogRef.current || e.button !== 0) return
    e.preventDefault()
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      originX: position.x,
      originY: position.y,
    }
    setIsDragging(true)
  }, [dialogRef, position.x, position.y])

  const moveDrag = useCallback((e) => {
    const dragState = dragRef.current
    if (!dragState) return

    const dialogHeight = dialogRef.current?.offsetHeight || DIALOG_FALLBACK_HEIGHT
    onPositionChange(clampPosition({
      x: dragState.originX + e.clientX - dragState.startX,
      y: dragState.originY + e.clientY - dragState.startY,
    }, dialogHeight))
  }, [clampPosition, dialogRef, onPositionChange])

  const endDrag = useCallback(() => {
    if (!dragRef.current) return
    dragRef.current = null
    setIsDragging(false)
  }, [])

  useEffect(() => {
    document.addEventListener('mousemove', moveDrag)
    document.addEventListener('mouseup', endDrag)
    return () => {
      document.removeEventListener('mousemove', moveDrag)
      document.removeEventListener('mouseup', endDrag)
    }
  }, [endDrag, moveDrag])

  useEffect(() => {
    const handleResize = () => {
      const dialogHeight = dialogRef.current?.offsetHeight || DIALOG_FALLBACK_HEIGHT
      onPositionChange(clampPosition(position, dialogHeight))
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [clampPosition, dialogRef, onPositionChange, position])

  return (
    <div
      ref={dialogRef}
      className={`ai-edit-dialog ${isDragging ? 'dragging' : ''}`}
      style={{
        position: 'fixed',
        left: `${position.x}px`,
        top: `${position.y}px`,
        zIndex: 1000
      }}
    >
      <div className="ai-edit-dialog-header" onMouseDown={startDrag}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
        </svg>
        <span>AI 修改</span>
        <button
          className="ai-edit-close"
          onMouseDown={(e) => e.stopPropagation()}
          onClick={onCancel}
          disabled={isSubmitting}
          aria-label="关闭 AI 修改"
        >
          ×
        </button>
      </div>
      <div className="ai-edit-dialog-body">
        <textarea
          className="ai-edit-input"
          value={request}
          onChange={(e) => onRequestChange(e.target.value)}
          placeholder="输入修改要求，如：改得更正式、删除这一段、扩写为一小段..."
          rows={3}
          disabled={isSubmitting}
          autoFocus
        />
        {error && (
          <div className="ai-edit-error">{error}</div>
        )}
      </div>
      <div className="ai-edit-dialog-footer">
        <button className="ai-edit-btn-cancel" onClick={onCancel} disabled={isSubmitting}>取消</button>
        <button
          className="ai-edit-btn-confirm"
          onClick={onSubmit}
          disabled={isSubmitting || !request.trim()}
        >
          {isSubmitting ? '修改中...' : '应用修改'}
        </button>
      </div>
    </div>
  )
}

export default AiEditDialog
