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
  activeEditor$,
  insertMarkdown$,
  realmPlugin,
} from '@mdxeditor/editor'
import '@mdxeditor/editor/style.css'
import {
  $createParagraphNode,
  $getRoot,
  $getSelection,
  $isRangeSelection,
  $setSelection,
  HISTORY_PUSH_TAG,
} from 'lexical'
import { useMemo } from 'react'
import {
  captureSelectionContext,
  insertPlainTextSelectionReplacement,
  shouldUsePlainTextInsertion,
} from '../../utils/selectionContext'

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

const aiSelectionBridgePlugin = realmPlugin({
  init(realm, params) {
    const bridgeRef = params?.bridgeRef
    if (!bridgeRef) return

    let capturedSelection = null

    bridgeRef.current = {
      capture() {
        const editor = realm.getValue(activeEditor$)
        let selectionSnapshot = null
        let selectionCapture = null

        editor?.getEditorState().read(() => {
          const selection = $getSelection()
          if ($isRangeSelection(selection) && !selection.isCollapsed()) {
            selectionSnapshot = selection.clone()
            selectionCapture = captureSelectionContext(selection, $getRoot())
          }
        })

        capturedSelection = selectionSnapshot && selectionCapture
          ? {
              editor,
              selectionSnapshot,
              isSingleBlockSelection: selectionCapture.isSingleBlockSelection,
            }
          : null
        return capturedSelection
          ? {
              selectedMarkdown: selectionCapture.selectedText,
              context: selectionCapture.requestContext,
            }
          : null
      },

      apply(replacementMarkdown) {
        if (!capturedSelection) {
          throw new Error('原选区已失效，请重新选择需要修改的内容')
        }

        const { editor, selectionSnapshot, isSingleBlockSelection } = capturedSelection
        if (!editor || realm.getValue(activeEditor$) !== editor) {
          capturedSelection = null
          throw new Error('编辑器焦点已变化，请重新选择需要修改的内容')
        }

        const replacement = replacementMarkdown ?? ''
        const insertAsPlainText = Boolean(
          replacement && shouldUsePlainTextInsertion(replacement, isSingleBlockSelection)
        )
        editor.update(() => {
          const restoredSelection = selectionSnapshot.clone()
          $setSelection(restoredSelection)

          if (!replacement) {
            const activeSelection = $getSelection()
            if (!$isRangeSelection(activeSelection) || activeSelection.isCollapsed()) {
              throw new Error('无法恢复原选区，请重新选择需要修改的内容')
            }
            activeSelection.removeText()

            // Lexical 会保留被清空块的类型（例如空标题会序列化为 "#"）。
            // 当选区覆盖了全文时，统一收敛为一个空正文块，确保保存的是真正空文章。
            const root = $getRoot()
            if (!root.getTextContent()) {
              root.clear()
              root.append($createParagraphNode())
            }
          } else if (insertAsPlainText) {
            const activeSelection = $getSelection()
            if (!$isRangeSelection(activeSelection) || activeSelection.isCollapsed()) {
              throw new Error('无法恢复原选区，请重新选择需要修改的内容')
            }
            insertPlainTextSelectionReplacement(activeSelection, replacement)
          }
        }, {
          discrete: true,
          ...((!replacement || insertAsPlainText) ? { tag: HISTORY_PUSH_TAG } : {}),
        })

        if (replacement && !insertAsPlainText) {
          realm.pub(insertMarkdown$, replacement)
        }
        capturedSelection = null
      },

      clear() {
        capturedSelection = null
      },
    }
  },
})

function AiEditToolbarButton({ onClick, disabled }) {
  return (
    <button
      type="button"
      title="AI 修改选中内容"
      aria-label="AI 修改选中内容"
      className="ai-edit-toolbar-button"
      disabled={disabled}
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

function MarkdownArticleEditor({
  editorRef,
  markdown,
  onChange,
  onAiEditRequest,
  selectionBridgeRef,
  interactionLocked = false,
}) {
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
          <AiEditToolbarButton onClick={onAiEditRequest} disabled={interactionLocked} />
          <Separator />
          <BoldItalicUnderlineToggles />
          <Separator />
          <ListsToggle options={['bullet', 'number']} />
        </>
      )
    }),
    aiSelectionBridgePlugin({ bridgeRef: selectionBridgeRef }),
  ], [interactionLocked, onAiEditRequest, selectionBridgeRef])

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
