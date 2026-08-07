from pathlib import Path

from desktop_agent.brain.knowledge.parser.python_parser import PythonParser

parser = PythonParser()

symbols = parser.parse(
    workspace="MYRAA",
    module="desktop_agent",
    file_path=Path("desktop_agent/main.py"),
)

for s in symbols:
    print(
        s.symbol_type,
        s.name,
        s.parent,
        s.line,
    )