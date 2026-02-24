from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


INCLUDE_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
}
EXCLUDE_PARTS = {
    ".git",
    "node_modules",
    "dist",
    ".turbo",
    "__pycache__",
    ".pytest_cache",
    ".venv",
}


@dataclass
class DifferentialReport:
    generated_at: str
    mcp_root: str
    a2a_root: str
    mcp_file_count: int
    a2a_file_count: int
    common_files: list[str]
    only_mcp_files: list[str]
    only_a2a_files: list[str]
    mcp_tools: list[str]
    a2a_tools: list[str]
    mapped_tools: dict[str, str]


def iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in EXCLUDE_PARTS for part in path.parts):
            continue
        if path.suffix not in INCLUDE_SUFFIXES:
            continue
        yield path


def parse_mcp_tools(manifest_path: Path) -> list[str]:
    if not manifest_path.exists():
        return []
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return sorted([tool["name"] for tool in data.get("tools", []) if "name" in tool])


def parse_a2a_tools(bootstrap_path: Path, extension_path: Path) -> list[str]:
    out: set[str] = set()
    for path in [bootstrap_path, extension_path]:
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for i, line in enumerate(lines):
            if line.strip() != "@mcp.tool()":
                continue
            if i + 1 >= len(lines):
                continue
            next_line = lines[i + 1].strip()
            if next_line.startswith("async def "):
                out.add(next_line.split("async def ", 1)[1].split("(", 1)[0])
    return sorted(out)


def build_tool_mapping() -> dict[str, str]:
    return {
        "agents.spawn": "spawn_agent",
        "repo.search": "search_repo",
        "twin.get_state": "get_twin_state",
        "twin.get_tasks": "get_twin_tasks",
    }


def render_markdown(report: DifferentialReport) -> str:
    common_preview = "\n".join(f"- `{item}`" for item in report.common_files[:12]) or "- (none)"
    only_mcp_preview = "\n".join(f"- `{item}`" for item in report.only_mcp_files[:12]) or "- (none)"
    only_a2a_preview = "\n".join(f"- `{item}`" for item in report.only_a2a_files[:12]) or "- (none)"
    mapping_rows = "\n".join(
        f"| `{k}` | `{v}` |" for k, v in sorted(report.mapped_tools.items())
    )

    return f"""# A2A Digital Twin Differential

Generated: {report.generated_at}

## Scope
- MCP root: `{report.mcp_root}`
- A2A root: `{report.a2a_root}`

## File Inventory
- MCP files: **{report.mcp_file_count}**
- A2A files: **{report.a2a_file_count}**
- Common relative paths: **{len(report.common_files)}**
- MCP-only relative paths: **{len(report.only_mcp_files)}**
- A2A-only relative paths: **{len(report.only_a2a_files)}**

## Tool Surfaces
- MCP tools: {", ".join(f"`{t}`" for t in report.mcp_tools) if report.mcp_tools else "(none)"}
- A2A tools: {", ".join(f"`{t}`" for t in report.a2a_tools) if report.a2a_tools else "(none)"}

## Phase-One Tool Mapping
| MCP Tool | A2A Source |
|---|---|
{mapping_rows}

## Common File Sample
{common_preview}

## MCP-only File Sample
{only_mcp_preview}

## A2A-only File Sample
{only_a2a_preview}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate MCP vs A2A differential report")
    parser.add_argument("--mcp-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--a2a-root",
        type=Path,
        default=(Path(__file__).resolve().parents[3] / "Airtable" / "a2a-digital-twin" / "a2a-digital-twin"),
    )
    parser.add_argument("--json-out", type=Path, default=Path("docs/a2a_digital_twin_differential.json"))
    parser.add_argument("--md-out", type=Path, default=Path("docs/a2a_digital_twin_differential.md"))
    args = parser.parse_args()

    mcp_root = args.mcp_root.resolve()
    a2a_root = args.a2a_root.resolve()

    mcp_files = [path.relative_to(mcp_root).as_posix() for path in iter_files(mcp_root)]
    a2a_files = [path.relative_to(a2a_root).as_posix() for path in iter_files(a2a_root)]

    mcp_set = set(mcp_files)
    a2a_set = set(a2a_files)

    report = DifferentialReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        mcp_root=str(mcp_root),
        a2a_root=str(a2a_root),
        mcp_file_count=len(mcp_files),
        a2a_file_count=len(a2a_files),
        common_files=sorted(mcp_set & a2a_set),
        only_mcp_files=sorted(mcp_set - a2a_set),
        only_a2a_files=sorted(a2a_set - mcp_set),
        mcp_tools=parse_mcp_tools(mcp_root / "mcp-manifest.json"),
        a2a_tools=parse_a2a_tools(
            a2a_root / "bootstrap_digital_twin.py",
            a2a_root / "mcp_extensions" / "claude_code_mcp_server.py",
        ),
        mapped_tools=build_tool_mapping(),
    )

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    args.md_out.write_text(render_markdown(report), encoding="utf-8")


if __name__ == "__main__":
    main()
