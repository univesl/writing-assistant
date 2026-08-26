from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml


_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
_RESOURCE_DIRS = ("references", "assets", "scripts")


class SkillValidationError(ValueError):
    pass


@dataclass(frozen=True)
class SkillDescriptor:
    name: str
    description: str
    path: Path
    instructions: str
    compatibility: str = ""
    allowed_tools: tuple[str, ...] = ()
    resources: tuple[str, ...] = ()
    status: str = "ready"
    missing_tools: tuple[str, ...] = ()
    disabled_scripts: tuple[str, ...] = ()
    capability_level: str = "instruction"
    managed: bool = True
    metadata: dict = field(default_factory=dict)


class SkillRegistry:
    """Read-only Agent Skills loader with strict path and tool validation."""

    def __init__(
        self,
        roots: Iterable[Path] | None = None,
        available_tools: Iterable[str] | None = None,
        script_executors: dict[str, object] | None = None,
    ):
        default_root = Path(__file__).resolve().parents[3] / "skills"
        env_root = os.getenv("AGENT_SKILLS_ROOT")
        if env_root:
            candidate = Path(env_root)
            if not candidate.is_absolute():
                candidate = (Path(__file__).resolve().parents[2] / candidate).resolve()
            default_root = candidate
        self.roots = [Path(root).resolve() for root in (roots or [default_root])]
        if available_tools is None:
            from .tool_registry import get_tool_registry

            available_tools = get_tool_registry().names()
        self.available_tools = set(available_tools)
        if script_executors is None:
            from .script_runner import registered_executors

            script_executors = registered_executors()
        self.script_executors = dict(script_executors or {})
        self._skills: dict[str, SkillDescriptor] = {}

    def load(self) -> dict[str, SkillDescriptor]:
        loaded: dict[str, SkillDescriptor] = {}
        for root in self.roots:
            if not root.exists():
                continue
            for skill_dir in sorted(path for path in root.iterdir() if path.is_dir()):
                skill_file = skill_dir / "SKILL.md"
                if skill_file.is_file():
                    descriptor = self._parse_skill(root, skill_dir, skill_file)
                    # Later roots intentionally override earlier roots.
                    loaded[descriptor.name] = descriptor
        self._skills = loaded
        return dict(loaded)

    def _parse_skill(self, root: Path, skill_dir: Path, skill_file: Path) -> SkillDescriptor:
        resolved_dir = skill_dir.resolve()
        if root != resolved_dir and root not in resolved_dir.parents:
            raise SkillValidationError(f"Skill path escapes configured root: {skill_dir}")
        if skill_file.stat().st_size > 10 * 1024 * 1024:
            raise SkillValidationError(f"SKILL.md is too large: {skill_file}")

        text = skill_file.read_text(encoding="utf-8")
        match = _FRONTMATTER_RE.match(text)
        if not match:
            raise SkillValidationError(f"Missing YAML frontmatter: {skill_file}")
        metadata = yaml.safe_load(match.group(1)) or {}
        if not isinstance(metadata, dict):
            raise SkillValidationError(f"Frontmatter must be a mapping: {skill_file}")
        extension_metadata = metadata.get("metadata") or {}
        if not isinstance(extension_metadata, dict):
            raise SkillValidationError(f"Frontmatter metadata must be a mapping: {skill_file}")

        name = str(metadata.get("name", "")).strip()
        description = str(metadata.get("description", "")).strip()
        if not _NAME_RE.fullmatch(name) or len(name) > 64:
            raise SkillValidationError(f"Invalid skill name: {name!r}")
        if name != skill_dir.name:
            raise SkillValidationError(f"Skill name must match directory: {skill_dir.name}")
        if not description or len(description) > 1024:
            raise SkillValidationError(f"Invalid skill description: {name}")

        allowed_tools_raw = metadata.get("allowed-tools", "")
        allowed_tools = tuple(str(allowed_tools_raw).split()) if allowed_tools_raw else ()
        missing_tools = tuple(tool for tool in allowed_tools if tool not in self.available_tools)

        resources: list[str] = []
        disabled_scripts: list[str] = []
        for resource_dir_name in _RESOURCE_DIRS:
            resource_dir = skill_dir / resource_dir_name
            if not resource_dir.exists():
                continue
            for resource in sorted(path for path in resource_dir.rglob("*") if path.is_file()):
                resolved_resource = resource.resolve()
                if resolved_dir not in resolved_resource.parents:
                    raise SkillValidationError(f"Resource escapes skill directory: {resource}")
                if resource.stat().st_size > 5 * 1024 * 1024:
                    raise SkillValidationError(f"Skill resource is too large: {resource}")
                relative = resource.relative_to(skill_dir).as_posix()
                resources.append(relative)
                if resource_dir_name == "scripts" and relative not in self.script_executors:
                    disabled_scripts.append(relative)

        app_metadata = extension_metadata.get("writing-assistant")
        if not isinstance(app_metadata, dict):
            app_metadata = extension_metadata
        workflow = app_metadata.get("workflow") if isinstance(app_metadata.get("workflow"), dict) else {}
        capability_level = "workflow" if workflow or allowed_tools else "instruction"
        if any(path.startswith("assets/") for path in resources):
            capability_level = "workflow"
        scripts_required = bool(app_metadata.get("scripts-required", False))
        status = (
            "incompatible"
            if missing_tools or (scripts_required and disabled_scripts)
            else "degraded"
            if disabled_scripts
            else "ready"
        )
        return SkillDescriptor(
            name=name,
            description=description,
            path=resolved_dir,
            instructions=match.group(2).strip(),
            # Accept the original project-level field while emitting new Skills
            # in the standard metadata extension namespace.
            compatibility=str(
                metadata.get("compatibility") or extension_metadata.get("compatibility", "")
            )[:500],
            allowed_tools=allowed_tools,
            resources=tuple(resources),
            status=status,
            missing_tools=missing_tools,
            disabled_scripts=tuple(disabled_scripts),
            capability_level=capability_level,
            managed=True,
            # ``metadata`` in the Agent Skills frontmatter is the extension
            # namespace.  Keep routing policy and provenance there instead of
            # exposing the reserved top-level fields a second time.
            metadata=dict(extension_metadata),
        )

    def reload(self) -> dict[str, SkillDescriptor]:
        """Reload operationally managed Skill files from configured roots.

        This method is intentionally not exposed as a public user API.  Ops may
        replace files on the server and restart or call this method from trusted
        maintenance code.
        """
        return self.load()

    def list(self) -> list[SkillDescriptor]:
        if not self._skills:
            self.load()
        return sorted(self._skills.values(), key=lambda skill: skill.name)

    def get(self, name: str) -> SkillDescriptor:
        if not self._skills:
            self.load()
        try:
            skill = self._skills[name]
        except KeyError as exc:
            raise SkillValidationError(f"Unknown skill: {name}") from exc
        if skill.status == "incompatible":
            raise SkillValidationError(
                f"Skill {name} requires unavailable tools: {', '.join(skill.missing_tools)}"
            )
        return skill

    def read_text_resources(
        self,
        skill: SkillDescriptor,
        directory: str = "references",
        max_total_chars: int = 20000,
        relative_paths: Iterable[str] | None = None,
    ) -> list[tuple[str, str]]:
        """Load only selected text references after a Skill has been chosen."""
        loaded: list[tuple[str, str]] = []
        total = 0
        selected = tuple(relative_paths) if relative_paths is not None else skill.resources
        known_resources = set(skill.resources)
        for relative in selected:
            if relative not in known_resources:
                raise SkillValidationError(f"Skill references an undeclared resource: {relative}")
            if not relative.startswith(f"{directory}/"):
                continue
            resource = (skill.path / relative).resolve()
            if skill.path not in resource.parents:
                raise SkillValidationError(f"Resource escapes skill directory: {relative}")
            if resource.suffix.lower() not in {".md", ".txt", ".yaml", ".yml", ".json"}:
                continue
            content = resource.read_text(encoding="utf-8")
            remaining = max_total_chars - total
            if remaining <= 0:
                break
            content = content[:remaining]
            loaded.append((relative, content))
            total += len(content)
        return loaded


_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
        _registry.load()
    return _registry
