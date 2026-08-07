from pathlib import Path

from desktop_agent.brain.knowledge.parser.javascript_parser import (
    JavaScriptParser,
)

ROOT = Path("electron")

for ext in ("*.js", "*.jsx", "*.mjs", "*.cjs"):

    for file in ROOT.rglob(ext):

        print("=" * 60)
        print(file)

        symbols = JavaScriptParser.parse(
            str(file),
            "MYRAA",
            "electron",
        )

        for s in symbols:
            print(s.symbol_type, s.name)