# calendar_manager.py
from .google_calendar_provider import GoogleCalendarProvider
from .o365_calendar_provider import O365CalendarProvider

class CalendarManager:
    def __init__(self):
        self.providers = {
            'google': GoogleCalendarProvider(),
#            'o365': O365CalendarProvider()
        }
        self.email_providers = {
            'lakeland@gmail.com': 'google',
            'corrin@morrissheetmetal.co.nz': 'google',
            'corrin.lakeland@countdown.co.nz': 'google',
#            'corrin.lakeland@cmeconnect.com': 'o365'
        }

    def authenticate(self, email):
        provider_name = self.email_providers.get(email)
        if provider_name:
            provider = self.providers.get(provider_name)
            if provider:
                provider.authenticate(email)
            else:
                print(f"No provider found for email: {email}")
        else:
            print(f"Email not registered: {email}")

    def create_meeting(self, email, meeting_data):
        provider_name = self.email_providers.get(email)
        if provider_name:
            provider = self.providers.get(provider_name)
            if provider:
                provider.create_meeting(email, meeting_data)
            else:
                print(f"No provider found for email: {email}")
        else:
            print(f"Email not registered: {email}")