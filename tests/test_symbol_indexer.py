from desktop_agent.brain.knowledge.database.knowledge_db import KnowledgeDB
from desktop_agent.brain.knowledge.indexer.symbol_indexer import SymbolIndexer


def main():

    db = KnowledgeDB()

    indexer = SymbolIndexer()

    modules = db.get_modules()

    print()

    print(f"Found {len(modules)} modules")

    print()

    total = 0

    for module_data in modules:

        class Module:
            pass

        module = Module()

        module.workspace = module_data["workspace"]
        module.name = module_data["name"]
        module.root = module_data["root"]

        print(f"Indexing {module.name}...")

        count = indexer.index(module)

        total += count

    print()

    print("=" * 50)
    print(f"TOTAL SYMBOLS INDEXED : {total}")
    print("=" * 50)

    print()

    rows = db.get_symbols()

    print(f"Database contains {len(rows)} symbols")


if __name__ == "__main__":
    main()