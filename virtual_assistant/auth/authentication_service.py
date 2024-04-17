class AuthenticationService:
    def __init__(self, providers):
        self.providers = providers

    def authenticate_user(self, email, provider_name):
        provider = self.providers.get(provider_name)
        if provider:
            return provider.authenticate(email)
        raise ValueError("Provider not supported")

    def get_user_credentials(self, email, provider_name):
        provider = self.providers.get(provider_name)
        if provider:
            return provider.get_credentials(email)
        raise ValueError("Provider not supported")
