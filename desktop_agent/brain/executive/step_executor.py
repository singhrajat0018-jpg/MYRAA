class StepExecutor:

    def __init__(self, tool_router):

        self.tool_router = tool_router

    def execute(self, step, context):

        return self.tool_router.execute(step)