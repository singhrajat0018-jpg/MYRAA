class ActionMatcher:

    def find_target(
        self,
        semantic_screen,
        text: str,
    ):

        for node in semantic_screen.nodes:

            if text.lower() in node.text.lower():

                return node

        return None