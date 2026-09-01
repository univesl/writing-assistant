# 深知公文写作 GitHub Public 发布说明

仓库地址：

https://github.com/dylanzhangzx/dknowc-official-doc-writer

## 简介

深知公文写作是面向单位办公室、综合岗、文秘、材料岗和企事业单位用户的正式材料写作 Agent Skill，支持公文写作、正式文书起草、汇报材料整理、讲话稿撰写、工作总结、方案报告生成、深知可信搜索、可信溯源报告和 Word 交付。

本 GitHub Public 版采用 skills.sh 渠道配置，不内置深知搜索 API Key。API Key 按需前置：不涉及深知搜索的任务（简单通知、改写、润色、审查、基于用户材料写作、只生成 Word 或红头文件）无需配置 Key 即可使用；仅当任务需要搜索政策、数据、案例依据时，才由 Agent 引导用户通过手机号验证码完成 MaaS 注册，并将 API Key 写入本机 `~/.zshrc` 中的 `DKNOWC_API_KEY` 配置块。

## GitHub Release 文案

Title:

v3.4.2 - GitHub public release

Body:

This is the skills.sh GitHub public release of 深知公文写作, an Agent Skill for Chinese official document writing, formal workplace writing, trusted material retrieval, and Word document delivery.

Highlights:

- Uses the skills.sh channel configuration.
- Adds local personal memory (`scripts/local_memory.py`): a personal material library (`knowledge-base/`, six fixed categories, keyword search) and writing preferences (`config/writing_preferences.json`, content/format/phrasing), both saved only after user confirmation, stored locally, and never included in the public package.
- Adds quote normalization in `scripts/format_document.py`: half-width quotes are auto-converted to full-width Chinese quotes during Word formatting; formal prose always uses full-width punctuation.
- All formal writing tasks now default to Word delivery; chat output only when the user explicitly asks for it.
- Adds fact-discipline rules (`reference/fact_discipline.md`) to keep facts at their given strength and avoid inventing unstated content.
- Adds anti-AI-pattern checks (`reference/anti_ai_patterns.md`) and a prose lint script (`scripts/prose_lint.py`).
- Expands standard files to 33 (English-named), covering statutory documents (decision, resolution, order, gazette, motion) and work materials (plan, summary, research report, etc.).
- Rebuilds `SKILL.md` with progressive loading and a reference-material table.
- API Key is on-demand: tasks without 深知可信搜索 no longer require configuring a Key; only search-dependent tasks guide MaaS registration, writing the key into `~/.zshrc` as `DKNOWC_API_KEY`.
- Adds existing-Word structure reading and format review via `scripts/review_document.py`.
- Upgrades source notes to a trusted traceability report HTML with clickable source markers, source cards, and knowledge-base links.
- Does not include any real API Key or local `config.ini`.

Users can manage MaaS usage at https://platform.dknowc.cn/.

## 推荐 GitHub Topics

```text
agent-skills
skills-sh
ai-writing
document-generation
chinese-writing
official-documents
policy-research
word-generation
dknowc
```
