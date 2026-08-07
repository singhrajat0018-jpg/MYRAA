LANGUAGE_SIGNATURES = {

    "Python": [
        ".py",
    ],

    "TypeScript": [
        ".ts",
        ".tsx",
    ],

    "JavaScript": [
        ".js",
        ".jsx",
        ".cjs",
        ".mjs",
    ],
}


FRAMEWORK_SIGNATURES = {

    "React": [
        "vite.config.ts",
        "vite.config.js",
        "package.json",
    ],

    "Electron": [
        "electron.vite.config.ts",
        "electron-builder.yml",
    ],

    "FastAPI": [
        "main.py",
    ],
}


ENTRY_POINTS = [

    "main.py",
    "server.py",
    "app.py",

    "main.ts",
    "main.js",

    "index.ts",
    "index.js",

    "electron.vite.config.ts",
]

import json
def save_module(self, module):

    cursor = self.conn.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO modules(
            workspace,
            name,
            root,
            languages,
            frameworks,
            dependencies,
            entry_points,
            package_managers,
            build_tools,
            confidence
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            module.workspace,
            module.name,
            module.root,
            json.dumps(module.languages),
            json.dumps(module.frameworks),
            json.dumps(module.dependencies),
            json.dumps(module.entry_points),
            json.dumps(module.package_managers),
            json.dumps(module.build_tools),
            module.confidence,
        ),
    )

    self.conn.commit()