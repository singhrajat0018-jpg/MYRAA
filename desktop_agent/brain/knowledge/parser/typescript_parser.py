"""
TypeScript Symbol Parser

Lightweight parser that extracts symbols from TypeScript source files.
This parser intentionally avoids heavy dependencies (tree-sitter/ts-morph)
and uses regex-based extraction for the first iteration.

Sprint 4:
- classes
- interfaces
- enums
- functions
- type aliases
- exported symbols
"""

from __future__ import annotations

import re
from pathlib import Path

from ..module_models.symbol_info import SymbolInfo


class TypeScriptParser:

    CLASS = re.compile(r"^\s*(export\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)")
    INTERFACE = re.compile(r"^\s*(export\s+)?interface\s+([A-Za-z_][A-Za-z0-9_]*)")
    ENUM = re.compile(r"^\s*(export\s+)?enum\s+([A-Za-z_][A-Za-z0-9_]*)")
    TYPE = re.compile(r"^\s*(export\s+)?type\s+([A-Za-z_][A-Za-z0-9_]*)")
    FUNCTION = re.compile(
        r"^\s*(export\s+)?(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)"
    )

    ARROW = re.compile(
        r"^\s*(export\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=.*=>"
    )

    @classmethod
    def parse(cls, file_path: str, workspace: str, module: str):

        symbols = []

        path = Path(file_path)

        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            return symbols

        for lineno, line in enumerate(lines, start=1):

            for symbol_type, pattern in (
                ("class", cls.CLASS),
                ("interface", cls.INTERFACE),
                ("enum", cls.ENUM),
                ("type", cls.TYPE),
                ("function", cls.FUNCTION),
                ("function", cls.ARROW),
            ):

                match = pattern.match(line)

                if not match:
                    continue

                exported = bool(match.group(1))
                name = match.group(2)

                symbols.append(
                    SymbolInfo(
                        workspace=workspace,
                        module=module,
                        file=file_path,
                        name=name,
                        symbol_type=symbol_type,
                        language="TypeScript",
                        line=lineno,
                        end_line=lineno,
                        parent=None,
                        signature=line.strip(),
                        decorators=[],
                        imports=[],
                        exported=exported,
                        confidence=0.95,
                    )
                )

        return symbols