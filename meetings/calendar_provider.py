from abc import ABC, abstractmethod

class CalendarProvider(ABC):
    @abstractmethod
    def authenticate(self, email):
        pass

    @abstractmethod
    def get_events(self, email):
        pass

    @abstractmethod
    def create_event(self, email, event_data):
        pass