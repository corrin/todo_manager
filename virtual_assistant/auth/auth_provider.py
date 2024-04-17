from abc import ABC, abstractmethod


class AuthProvider(ABC):
    @abstractmethod
    def authenticate(self, email):
        """Authenticate a user and store/update credentials."""
        pass

    @abstractmethod
    def get_credentials(self, email):
        """Retrieve stored credentials for the specified user."""
        pass

    @abstractmethod
    def store_credentials(self, email, credentials):
        """Store or update user credentials."""
        pass
