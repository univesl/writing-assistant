from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ToolDescriptor:
    """A server-owned capability that a managed Skill may request.

    Skills can select these capabilities, but they never provide the executable
    implementation.  This keeps operationally installed Skills useful without
    turning the web application into a general script runner.
    """

    name: str
    description: str
    deterministic: bool = True
    mutates_document: bool = False


class ToolRegistry:
    def __init__(self, tools: Iterable[ToolDescriptor] | None = None):
        self._tools = {tool.name: tool for tool in (tools or DEFAULT_TOOLS)}

    def names(self) -> set[str]:
        return set(self._tools)

    def get(self, name: str) -> ToolDescriptor:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ValueError(f"Unknown built-in tool: {name}") from exc

    def list(self) -> list[ToolDescriptor]:
        return sorted(self._tools.values(), key=lambda tool: tool.name)


DEFAULT_TOOLS = (
    ToolDescriptor("kng_search", "查询当前 KnG 服务中的公文依据", deterministic=False),
    ToolDescriptor("web_search", "查询公开互联网中的可追溯资料", deterministic=False),
    ToolDescriptor("document_linter", "检查公文结构、编号、日期和落款"),
    ToolDescriptor("reference_parser", "解析运维允许的 PDF、DOCX、Markdown 和文本附件"),
    ToolDescriptor("format_linter", "检查正文是否满足所选公文版式配置"),
    ToolDescriptor("docx_renderer", "使用服务端内置渲染器生成 DOCX", mutates_document=False),
)


_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
