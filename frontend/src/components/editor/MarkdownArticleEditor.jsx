import {
  MDXEditor,
  headingsPlugin,
  listsPlugin,
  quotePlugin,
  tablePlugin,
  thematicBreakPlugin,
  linkPlugin,
  linkDialogPlugin,
  markdownShortcutPlugin,
  toolbarPlugin,
  UndoRedo,
  BoldItalicUnderlineToggles,
  BlockTypeSelect,
  ListsToggle,
  Separator,
} from '@mdxeditor/editor'
import '@mdxeditor/editor/style.css'
import { useMemo } from 'react'

const EDITOR_TRANSLATIONS = {
  'toolbar.undo': '撤销 {{shortcut}}',
  'toolbar.redo': '重做 {{shortcut}}',
  'toolbar.bold': '加粗',
  'toolbar.removeBold': '取消加粗',
  'toolbar.italic': '斜体',
  'toolbar.removeItalic': '取消斜体',
  'toolbar.underline': '下划线',
  'toolbar.removeUnderline': '取消下划线',
  'toolbar.bulletedList': '项目列表',
  'toolbar.numberedList': '编号列表',
  'toolbar.toggleGroup': '格式按钮组',
  'toolbar.blockTypes.paragraph': '正文',
  'toolbar.blockTypes.quote': '引用',
  'toolbar.blockTypes.heading': '{{level}} 级标题',
  'toolbar.blockTypeSelect.selectBlockTypeTooltip': '选择段落类型',
  'toolbar.blockTypeSelect.placeholder': '段落类型',
}

function translateEditor(key, defaultValue, interpolations = {}) {
  let text = EDITOR_TRANSLATIONS[key] || defaultValue
  Object.entries(interpolations).forEach(([name, value]) => {
    text = text.replaceAll(`{{${name}}}`, String(value))
  })
  return text
}

function AiEditToolbarButton({ onClick }) {
  return (
    <button
      type="button"
      title="AI 修改选中内容"
      aria-label="AI 修改选中内容"
      className="ai-edit-toolbar-button"
      onMouseDown={(event) => {
        event.preventDefault()
      }}
      onClick={onClick}
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3z" />
        <path d="M19 14l.8 2.2L22 17l-2.2.8L19 20l-.8-2.2L16 17l2.2-.8L19 14z" />
        <path d="M5 14l.8 2.2L8 17l-2.2.8L5 20l-.8-2.2L2 17l2.2-.8L5 14z" />
      </svg>
      <span>AI 修改</span>
    </button>
  )
}

function MarkdownArticleEditor({ editorRef, markdown, onChange, onAiEditRequest }) {
  const editorPlugins = useMemo(() => [
    headingsPlugin(),
    listsPlugin(),
    quotePlugin(),
    tablePlugin(),
    thematicBreakPlugin(),
    linkPlugin(),
    linkDialogPlugin(),
    markdownShortcutPlugin(),
    toolbarPlugin({
      toolbarContents: () => (
        <>
          <UndoRedo />
          <Separator />
          <BlockTypeSelect />
          <Separator />
          <AiEditToolbarButton onClick={onAiEditRequest} />
          <Separator />
          <BoldItalicUnderlineToggles />
          <Separator />
          <ListsToggle options={['bullet', 'number']} />
        </>
      )
    }),
  ], [onAiEditRequest])

  return (
    <MDXEditor
      ref={editorRef}
      markdown={markdown}
      onChange={onChange}
      plugins={editorPlugins}
      translation={translateEditor}
      placeholder="在此编辑 AI 生成的内容..."
      className="wysiwyg-markdown-editor"
      contentEditableClassName="wysiwyg-markdown-content"
    />
  )
}

export default MarkdownArticleEditor
