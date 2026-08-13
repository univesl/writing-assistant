import { useCallback, useEffect, useRef, useState } from 'react'

function EditorToc({ items, contentRef }) {
  const [tocWidth, setTocWidth] = useState(250)
  const isResizingRef = useRef(false)

  const startResizing = (e) => {
    isResizingRef.current = true
    e.preventDefault()
  }

  const resize = useCallback((e) => {
    if (!isResizingRef.current) return

    const tocSidebar = document.querySelector('.toc-sidebar')
    const rect = tocSidebar?.getBoundingClientRect()
    if (!rect) return

    const newWidth = e.clientX - rect.left
    const maxWidth = window.innerWidth * 0.5
    if (newWidth >= 180 && newWidth <= maxWidth) {
      setTocWidth(newWidth)
    }
  }, [])

  const stopResizing = useCallback(() => {
    isResizingRef.current = false
  }, [])

  useEffect(() => {
    document.addEventListener('mousemove', resize)
    document.addEventListener('mouseup', stopResizing)
    return () => {
      document.removeEventListener('mousemove', resize)
      document.removeEventListener('mouseup', stopResizing)
    }
  }, [resize, stopResizing])

  const scrollToHeading = (item) => {
    const headings = contentRef.current?.querySelectorAll('.mdxeditor-root-contenteditable h1, .mdxeditor-root-contenteditable h2, .mdxeditor-root-contenteditable h3, .mdxeditor-root-contenteditable h4, .mdxeditor-root-contenteditable h5, .mdxeditor-root-contenteditable h6')
    const headingElement = headings?.[item.headingIndex]
    headingElement?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <>
      <div className="resize-handle left-resize" onMouseDown={startResizing} />
      <div className="toc-sidebar" style={{ width: `${tocWidth}px` }}>
        <div className="toc-header">
          <h4>目录</h4>
        </div>
        {items.length > 0 ? (
          <ul className="toc-list">
            {items.map((item) => (
              <li
                key={item.id}
                className={`toc-item level-${item.level} ${item.isMainTitle ? 'toc-main-title' : ''}`}
                onClick={() => scrollToHeading(item)}
              >
                {item.text}
              </li>
            ))}
          </ul>
        ) : (
          <div className="empty-toc">暂无目录</div>
        )}
      </div>
    </>
  )
}

export default EditorToc
