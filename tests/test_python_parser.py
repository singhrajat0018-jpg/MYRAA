from pathlib import Path

from desktop_agent.brain.knowledge.parser.python_parser import PythonParser


def test_python_parser_extracts_classes_functions_and_methods(tmp_path: Path):
    source = tmp_path / "sample.py"
    source.write_text(
        "class Assistant:\n"
        "    def speak(self):\n"
        "        pass\n\n"
        "async def listen():\n"
        "    pass\n",
        encoding="utf-8",
    )

    symbols = PythonParser().parse("MYRAA", "desktop_agent", source)

    assert [(symbol.symbol_type, symbol.name, symbol.parent) for symbol in symbols] == [
        ("class", "Assistant", None),
        ("method", "speak", "Assistant"),
        ("function", "listen", None),
    ]
