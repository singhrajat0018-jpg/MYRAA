from pathlib import Path

from desktop_agent.brain.knowledge.parser.typescript_parser import (
    TypeScriptParser,
)

ROOT = Path("src")

for file in ROOT.rglob("*.ts"):

    print("=" * 60)
    print(file)

    symbols = TypeScriptParser.parse(
        str(file),
        "MYRAA",
        "src",
    )

    for s in symbols:
        print(s.symbol_type, s.name)