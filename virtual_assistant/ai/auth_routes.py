from flask import Blueprint, request, render_template, redirect, url_for, flash
from virtual_assistant.utils.user_manager import UserManager
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
                email = UserManager.get_current_user()
                provider_instance = ai_manager.get_provider(provider)
                if not provider_instance:
                    flash(f'Unknown provider: {provider}')
                    return redirect(url_for('main_app'))

                provider_instance.store_credentials(email, {"api_key": api_key})
                flash(f'{provider} credentials saved successfully')
                return redirect(url_for('main_app'))
            except Exception as e:
                logger.error(f"Error saving {provider} credentials: {e}")
                flash('Error saving credentials')
                return redirect(url_for('ai_auth.setup_credentials', provider=provider))

        # GET request - show setup form
        template_name = f"{provider}_setup.html"
        return render_template(template_name)

    return bp