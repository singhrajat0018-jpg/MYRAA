


class ProjectBrain:

    def __init__(self, project_context):

        self.project_context = project_context

    # --------------------------------------------------

    def describe(self, project_name: str):

        return self.project_context.get_project(project_name)

    # --------------------------------------------------

    def languages(self, project_name: str):

        ctx = self.describe(project_name)

        if ctx is None:
            return []

        return ctx.languages

    # --------------------------------------------------

    def frameworks(self, project_name: str):

        ctx = self.describe(project_name)

        if ctx is None:
            return []

        return ctx.frameworks

    # --------------------------------------------------

    def entry_points(self, project_name: str):

        ctx = self.describe(project_name)

        if ctx is None:
            return []

        return ctx.entry_points