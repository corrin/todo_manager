from abc import ABC, abstractmethod

class CalendarProvider(ABC):
    @abstractmethod
    def authenticate(self, email):
        pass

    @abstractmethod
    def get_meetings(self, email):
        pass

    @abstractmethod
    def create_meeting(self, email, event_data):
        pass