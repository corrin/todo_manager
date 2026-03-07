from flask import Blueprint, flash, jsonify, redirect, request, url_for
from flask_login import current_user, login_required
from virtual_assistant.database.database import Database
from virtual_assistant.database.external_account import ExternalAccount
from virtual_assistant.utils.logger import logger

database_bp = Blueprint("database", __name__, url_prefix="/database")


@database_bp.route("/test_sqlite", methods=["GET"])
def test_sqlite():
    # Call the test_sqlite method from the Database class
    return Database.get_instance().test_sqlite()


@database_bp.route("/remove_external_account", methods=["POST"])
@login_required
def remove_external_account():
    """Remove an external account (calendar or tasks)."""
    try:
        account_id = request.form.get("account_id")
        account_type = request.form.get("account_type")  # 'calendar' or 'tasks'
        
        if not account_id:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"success": False, "error": "Account ID required"}), 400
            flash("Account ID is required", "error")
            return redirect(url_for("settings"))
            
        if account_type not in ('calendar', 'tasks'):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"success": False, "error": "Invalid account type"}), 400
            flash("Invalid account type", "error")
            return redirect(url_for("settings"))
            
        # Get the account
        account = ExternalAccount.query.get(account_id)
        if not account or account.user_id != current_user.id:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"success": False, "error": "Account not found"}), 404
            flash("Account not found", "error")
            return redirect(url_for("settings"))
            
        # Check if this is a primary account
        was_primary = (account.is_primary_calendar if account_type == 'calendar'
                      else account.is_primary_tasks)
                      
        # Delete the account
        ExternalAccount.delete_by_email_and_provider(
            account.account_email,
            account.provider,
            current_user.id
        )
        
        # If this was primary, set another account as primary if available
        if was_primary:
            # Find first remaining account of same type
            filter_condition = (
                (ExternalAccount.use_for_calendar == True) if account_type == 'calendar'
                else (ExternalAccount.use_for_tasks == True)
            )
            new_primary = ExternalAccount.query.filter(
                ExternalAccount.user_id == current_user.id,
                filter_condition
            ).first()
            
            if new_primary:
                ExternalAccount.set_as_primary(
                    new_primary.account_email,
                    new_primary.provider,
                    current_user.id,
                    account_type
                )
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": True})
            
        flash(f"Successfully removed {account_type} account", "success")
        return redirect(url_for("settings"))
        
    except Exception as e:
        logger.error(f"Error removing external account: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": False, "error": str(e)}), 500
        flash("Error removing account", "error")
        return redirect(url_for("settings"))
