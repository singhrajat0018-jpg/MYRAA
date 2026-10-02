from pathlib import Path

from desktop_agent.brain.knowledge.parser.typescript_parser import TypeScriptParser


def test_typescript_parser_extracts_supported_symbols(tmp_path: Path):
    source = tmp_path / "sample.ts"
    source.write_text(
        "export interface Settings {}\n"
        "type Mode = 'voice'\n"
        "export enum Route { Live }\n"
        "class Client {}\n"
        "export function connect() {}\n"
        "const helper = () => {}\n",
        encoding="utf-8",
    )

    symbols = TypeScriptParser.parse(str(source), "MYRAA", "src")

    assert [(symbol.symbol_type, symbol.name, symbol.exported) for symbol in symbols] == [
        ("interface", "Settings", True),
        ("type", "Mode", False),
        ("enum", "Route", True),
        ("class", "Client", False),
        ("function", "connect", True),
        ("function", "helper", False),
    ]
