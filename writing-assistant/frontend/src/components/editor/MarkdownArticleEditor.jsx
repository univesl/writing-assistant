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
  $createRangeSelectionFromDom,
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
  createPreparedSelectionStore,
  insertPlainTextSelectionReplacement,
  selectionTextsMatch,
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
        const rootElement = editor?.getRootElement?.()
        const domSelection = rootElement?.ownerDocument?.defaultView?.getSelection?.()
        const nativeSelectionIsUsable = Boolean(
          domSelection &&
          domSelection.rangeCount > 0 &&
          !domSelection.isCollapsed &&
          domSelection.anchorNode &&
          domSelection.focusNode &&
          rootElement.contains(domSelection.anchorNode) &&
          rootElement.contains(domSelection.focusNode)
        )
        const nativeSelectedText = nativeSelectionIsUsable ? domSelection.toString() : ''
        let selectionSnapshot = null
        let selectionCapture = null
        let captureError = ''

        editor?.getEditorState().read(() => {
          // 首选从浏览器当前真实高亮范围重建 Lexical 选区。若复杂块边界无法直接
          // 转换，才允许使用编辑器缓存选区，而且其可见字符必须与浏览器高亮完全一致。
          const domRangeSelection = nativeSelectionIsUsable
            ? $createRangeSelectionFromDom(domSelection, editor)
            : null
          const cachedSelection = $getSelection()
          const selectionCandidates = [domRangeSelection, cachedSelection]
          const selection = selectionCandidates.find(candidate => (
            $isRangeSelection(candidate) &&
            !candidate.isCollapsed() &&
            selectionTextsMatch(nativeSelectedText, candidate.getTextContent())
          ))

          if ($isRangeSelection(selection) && !selection.isCollapsed()) {
            const lexicalSelectedText = selection.getTextContent()
            selectionSnapshot = selection.clone()
            selectionCapture = captureSelectionContext(selection, $getRoot())
            if (selectionCapture) {
              // 侧栏和模型必须看到浏览器中实际高亮的文字，而不是编辑器重序列化的父块。
              selectionCapture.selectedText = nativeSelectedText
              selectionCapture.lexicalSelectedText = lexicalSelectedText
            }
          } else if (nativeSelectionIsUsable) {
            captureError = '编辑器未能定位完整选区，文章未作修改；请重新拖选一次'
          }
        })

        capturedSelection = selectionSnapshot && selectionCapture
          ? {
              editor,
              selectionSnapshot,
              isSingleBlockSelection: selectionCapture.isSingleBlockSelection,
              lexicalSelectedText: selectionCapture.lexicalSelectedText,
            }
          : null
        if (captureError) {
          return { error: captureError }
        }
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

        const {
          editor,
          selectionSnapshot,
          isSingleBlockSelection,
          lexicalSelectedText,
        } = capturedSelection
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

          const activeSelection = $getSelection()
          if (
            !$isRangeSelection(activeSelection) ||
            activeSelection.isCollapsed() ||
            !selectionTextsMatch(activeSelection.getTextContent(), lexicalSelectedText)
          ) {
            throw new Error('无法精确恢复原选区，文章未作修改；请重新选择需要修改的内容')
          }

          if (!replacement) {
            activeSelection.removeText()

            // Lexical 会保留被清空块的类型（例如空标题会序列化为 "#"）。
            // 当选区覆盖了全文时，统一收敛为一个空正文块，确保保存的是真正空文章。
            const root = $getRoot()
            if (!root.getTextContent()) {
              root.clear()
              root.append($createParagraphNode())
            }
          } else if (insertAsPlainText) {
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

function AiEditToolbarButton({ onPrepare, onActivate, disabled }) {
  const preparedSelectionStore = useMemo(() => createPreparedSelectionStore(), [])

  const prepareSelection = () => {
    preparedSelectionStore.prepare(onPrepare)
  }

  const discardPreparedSelection = () => {
    preparedSelectionStore.clear()
  }

  const activatePreparedSelection = () => {
    // 键盘触发没有 pointerdown；此时仍尝试读取一次当前真实选区。
    const selected = preparedSelectionStore.consume(onPrepare)
    onActivate?.(selected)
  }

  return (
    <button
      type="button"
      title="AI 修改选中内容"
      aria-label="AI 修改选中内容"
      className="ai-edit-toolbar-button"
      disabled={disabled}
      onPointerDown={(event) => {
        if (!event.isPrimary || event.button !== 0) return
        event.preventDefault()
        // pointerdown 的默认聚焦发生前，原生高亮仍然精确对应用户拖选范围。
        // 这里只冻结快照，不打开对话框，也不触发任何 React 状态更新。
        prepareSelection()
      }}
      onMouseDown={(event) => {
        if (event.button !== 0) return
        event.preventDefault()
        // 兼容没有 Pointer Events 的环境，同时避免 pointerdown 后重复捕获。
        if (!preparedSelectionStore.hasPrepared()) prepareSelection()
      }}
      onPointerCancel={discardPreparedSelection}
      onClick={activatePreparedSelection}
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
  onAiEditPrepare,
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
          <AiEditToolbarButton
            onPrepare={onAiEditPrepare}
            onActivate={onAiEditRequest}
            disabled={interactionLocked}
          />
          <Separator />
          <BoldItalicUnderlineToggles />
          <Separator />
          <ListsToggle options={['bullet', 'number']} />
        </>
      )
    }),
    aiSelectionBridgePlugin({ bridgeRef: selectionBridgeRef }),
  ], [interactionLocked, onAiEditPrepare, onAiEditRequest, selectionBridgeRef])

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
