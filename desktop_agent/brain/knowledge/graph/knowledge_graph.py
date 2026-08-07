from .node import GraphNode
from .edge import GraphEdge


class KnowledgeGraph:

    def __init__(self):

        self.nodes = {}

        self.edges = []

    # ----------------------------------------

    def add_node(self, node: GraphNode):

        self.nodes[node.id] = node

    # ----------------------------------------

    def add_edge(self, edge: GraphEdge):

        self.edges.append(edge)

    # ----------------------------------------

    def get_node(self, node_id):

        return self.nodes.get(node_id)

    # ----------------------------------------

    def neighbors(self, node_id):

        result = []

        for edge in self.edges:

            if edge.source == node_id:

                result.append(
                    self.nodes.get(edge.target)
                )

        return result