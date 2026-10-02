from pathlib import Path

from desktop_agent.brain.knowledge.parser.javascript_parser import JavaScriptParser


def test_javascript_parser_extracts_supported_symbols(tmp_path: Path):
    source = tmp_path / "sample.js"
    source.write_text(
        "export class Bridge {}\n"
        "function boot() {}\n"
        "export const route = () => {}\n",
        encoding="utf-8",
    )

    symbols = JavaScriptParser.parse(str(source), "MYRAA", "electron")

    assert [(symbol.symbol_type, symbol.name, symbol.exported) for symbol in symbols] == [
        ("class", "Bridge", True),
        ("function", "boot", False),
        ("function", "route", True),
    ]
