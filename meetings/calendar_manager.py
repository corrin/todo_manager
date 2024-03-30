# calendar_manager.py
from .google_calendar_provider import GoogleCalendarProvider
from .o365_calendar_provider import O365CalendarProvider
from utils.logger import logger


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
                logger.debug(f"Authenticating with {provider_name} provider for email: {email}")
                instructions = provider.authenticate(email)
                if instructions:
                    logger.debug(f"Received instructions: {instructions}")
                    return instructions
                else:
                    logger.debug(f"No instructions received from {provider_name} provider for email: {email}")
            else:
                logger.warning(f"No provider found for email: {email}")
        else:
            logger.warning(f"Email not registered: {email}")
        return None

    def create_meeting(self, email, meeting_data):
        provider_name = self.email_providers.get(email)

        if provider_name:
            provider = self.providers.get(provider_name)
            if provider:
                provider.create_meeting(email, meeting_data)
            else:
                logger.warning(f"No provider found for email: {email}")
        else:
            logger.warning(f"Email not registered: {email}")