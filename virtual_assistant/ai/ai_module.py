from abc import abstractmethod


class AIInterface:
    @abstractmethod
    def generate_text(self, prompt):
        """Generate text based on the provided prompt"""
        pass

    # Other common methods for interacting with the AI service
