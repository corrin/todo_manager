from flask import Blueprint, request, render_template, redirect, url_for, flash
from virtual_assistant.database.user_manager import UserDataManager
from virtual_assistant.utils.logger import logger
from .ai_manager import AIManager


def init_ai_routes():
    """Initialize routes for AI provider authentication."""
    bp = Blueprint('ai_auth', __name__, url_prefix='/ai_auth')
    ai_manager = AIManager()

    @bp.route('/setup/<provider>', methods=['GET', 'POST'])
    def setup_credentials(provider):
        """Handle credential setup for AI providers."""
        if request.method == 'POST':
            api_key = request.form.get('api_key')
            if not api_key:
                flash('API key is required')
                return redirect(url_for('ai_auth.setup_credentials', provider=provider))
            
            try:
                app_login = UserDataManager.get_current_user() # Use correct manager and variable name
                provider_instance = ai_manager.get_provider(provider)
                if not provider_instance:
                    flash(f'Unknown provider: {provider}')
                    return redirect(url_for('index'))
                
                # Assuming AI providers also need app_login for credential storage context
                provider_instance.store_credentials(app_login, {"api_key": api_key}) # Use app_login
                flash(f'{provider} credentials saved successfully')
                return redirect(url_for('index'))
            except Exception as e:
                logger.error(f"Error saving {provider} credentials: {e}")
                flash('Error saving credentials')
                return redirect(url_for('ai_auth.setup_credentials', provider=provider))

        # GET request - show setup form
        template_name = f"{provider}_setup.html"
        return render_template(template_name)

    return bp