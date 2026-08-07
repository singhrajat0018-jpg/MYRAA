import ast
from pathlib import Path

from ..module_models.symbol_info import SymbolInfo


class PythonParser:

    def parse(
        self,
        workspace: str,
        module: str,
        file_path: Path,
    ) -> list[SymbolInfo]:

        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)

        return self._visit(
            tree,
            workspace,
            module,
            file_path,
        )

    def _visit(
        self,
        tree,
        workspace,
        module,
        file_path,
    ):

        visitor = PythonVisitor(
            workspace,
            module,
            file_path,
        )

        visitor.visit(tree)

        return visitor.symbols


class PythonVisitor(ast.NodeVisitor):

    def __init__(self, workspace, module, file_path):

        self.workspace = workspace
        self.module = module
        self.file_path = str(file_path)

        self.symbols = []
        self.parent_stack = []

    # ------------------------------------------------

    def visit_ClassDef(self, node):

        self.symbols.append(
            SymbolInfo(
                workspace=self.workspace,
                module=self.module,
                file=self.file_path,
                name=node.name,
                symbol_type="class",
                language="Python",
                line=node.lineno,
                end_line=getattr(node, "end_lineno", node.lineno),
                parent=None,
                signature="",
                decorators=[ast.unparse(d) for d in node.decorator_list],
                imports=[],
                exported=True,
                confidence=1.0,
            )
        )

        self.parent_stack.append(node.name)
        self.generic_visit(node)
        self.parent_stack.pop()

    # ------------------------------------------------

    def visit_FunctionDef(self, node):

        self.symbols.append(
            SymbolInfo(
                workspace=self.workspace,
                module=self.module,
                file=self.file_path,
                name=node.name,
                symbol_type="method" if self.parent_stack else "function",
                language="Python",
                line=node.lineno,
                end_line=getattr(node, "end_lineno", node.lineno),
                parent=self.parent_stack[-1] if self.parent_stack else None,
                signature="",
                decorators=[ast.unparse(d) for d in node.decorator_list],
                imports=[],
                exported=True,
                confidence=1.0,
            )
        )

        self.generic_visit(node)

    # ------------------------------------------------

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)