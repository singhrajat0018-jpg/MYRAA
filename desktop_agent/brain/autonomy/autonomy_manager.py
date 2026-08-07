class AutonomyManager:

    def __init__(self):

        self.current = None

    def submit(self, initiative):

        if self.current == initiative.title:
            return False

        self.current = initiative.title

        return True

    def complete(self):

        self.current = None