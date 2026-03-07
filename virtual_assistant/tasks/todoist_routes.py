from flask import Blueprint, flash, jsonify, redirect, request, url_for
from flask_login import current_user

from virtual_assistant.database.database import db
from virtual_assistant.database.external_account import ExternalAccount
from virtual_assistant.tasks.task_manager import TaskManager
from virtual_assistant.utils.logger import logger

from .todoist_provider import TodoistProvider


def _get_task_manager():
    return TaskManager()


_DEFAULT_INSTRUCTIONS = """AI Instructions:
- Schedule friend catchups weekly
- Work on each project at least twice a week
- Keep mornings free for focused work
- Handle urgent tasks within 24 hours"""


def _create_default_instruction_task(submitted_email):
    """Attempt to create a default AI instruction task for a Todoist account."""
    task_manager = _get_task_manager()
    todoist_provider = task_manager.get_provider("todoist")
    if todoist_provider:
        todoist_provider.create_instruction_task(current_user.id, submitted_email, _DEFAULT_INSTRUCTIONS)
        logger.info(f"Created default AI instruction task for account {submitted_email}")
    else:
        logger.warning("Todoist provider not found, cannot create instruction task.")


def init_todoist_routes():
    """Initializes the Blueprint for Todoist authentication and account management."""
    bp = Blueprint("todoist_auth", __name__, url_prefix="/todoist_auth")

    @bp.route("/add_account", methods=["POST"])
    def add_account():
        """Handles the submission from the 'Add Todoist Account' modal."""
        app_login = current_user.app_login
        submitted_email = request.form.get("todoist_email")
        submitted_api_key = request.form.get("api_key")

        if not submitted_email or not submitted_api_key:
            flash(
                "Both Todoist email and API key are required to add an account.",
                "danger",
            )
            return redirect(url_for("settings"))

        try:
            existing_ext_account = ExternalAccount.get_task_account(current_user.id, "todoist", submitted_email)
            if existing_ext_account:
                flash(
                    f"A Todoist account for {submitted_email} already exists.",
                    "warning",
                )
                return redirect(url_for("settings"))

            ext_account = ExternalAccount.set_task_account(
                user_id=current_user.id,
                provider_name="todoist",
                task_user_email=submitted_email,
                credentials={"api_key": submitted_api_key},
            )
            db.session.commit()
            flash(f"Todoist account for {submitted_email} added successfully.", "success")
            logger.info(f"Added Todoist account {submitted_email} for user {app_login}")

            try:
                _create_default_instruction_task(submitted_email)
            except Exception as instruction_error:
                logger.error(f"Failed to create default instruction task for {submitted_email}: {instruction_error}")
                flash(
                    f"Account added, but failed to create default Todoist instruction task: {instruction_error}",
                    "warning",
                )

        except Exception as e:
            db.session.rollback()
            logger.exception(f"Error adding Todoist account {submitted_email} for {app_login}: {e}")
            flash(
                f"Error adding Todoist account for {submitted_email}. Please check the details and try again.",
                "danger",
            )

        return redirect(url_for("settings"))

    @bp.route("/update_key", methods=["POST"])
    def update_key():
        """Handles the submission from the 'Edit Todoist API Key' modal."""
        app_login = current_user.app_login
        submitted_email = request.form.get("todoist_email")
        submitted_api_key = request.form.get("api_key")

        if not submitted_email:
            flash("Todoist account email is missing. Cannot update key.", "danger")
            return redirect(url_for("settings"))

        try:
            ext_account = ExternalAccount.set_task_account(
                user_id=current_user.id,
                provider_name="todoist",
                task_user_email=submitted_email,
                credentials={"api_key": submitted_api_key},
            )
            if ext_account:
                db.session.commit()
                flash(f"API key for Todoist account {submitted_email} updated.", "success")
                logger.info(f"Updated Todoist API key for account {submitted_email}, user {app_login}")

                if submitted_api_key:
                    try:
                        _create_default_instruction_task(submitted_email)
                    except Exception as instruction_error:
                        logger.error(
                            f"Failed to create default instruction task for {submitted_email}: {instruction_error}"
                        )
                        flash(
                            f"Key updated, but failed to create default Todoist instruction task: {instruction_error}",
                            "warning",
                        )
            else:
                flash(
                    f"Todoist account for {submitted_email} not found. Cannot update key.",
                    "danger",
                )
                logger.error(f"Todoist account {submitted_email} not found for update for user {app_login}")

        except Exception as e:
            db.session.rollback()
            logger.exception(f"Error updating Todoist key for {submitted_email}, user {app_login}: {e}")
            flash(f"Error updating API key for {submitted_email}.", "danger")

        return redirect(url_for("settings"))

    @bp.route("/delete_account", methods=["POST"])
    def delete_account():
        """Handles the submission from the 'Delete Todoist Account' modal."""
        app_login = current_user.app_login
        submitted_email = request.form.get("todoist_email")

        if not submitted_email:
            flash("Todoist account email is missing. Cannot delete.", "danger")
            return redirect(url_for("settings"))

        try:
            deleted = ExternalAccount.delete_task_account(current_user.id, "todoist", submitted_email)

            if deleted:
                db.session.commit()
                flash(
                    f"Todoist account for {submitted_email} deleted successfully.",
                    "success",
                )
                logger.info(f"Deleted Todoist account {submitted_email} for user {app_login}")
            else:
                flash(f"Todoist account for {submitted_email} not found.", "warning")
                logger.warning(
                    f"Attempted to delete non-existent Todoist account {submitted_email} for user {app_login}"
                )

        except Exception as e:
            db.session.rollback()
            logger.exception(f"Error deleting Todoist account {submitted_email} for {app_login}: {e}")
            flash(f"Error deleting Todoist account for {submitted_email}.", "danger")

        return redirect(url_for("settings"))

    @bp.route("/test", methods=["POST"])
    def test_connection():
        """Test a Todoist API key without saving it."""
        api_key = request.form.get("api_key")
        if not api_key:
            return jsonify({"success": False, "message": "API key is required"})

        try:
            from todoist_api_python.api import TodoistAPI

            api = TodoistAPI(api_key)
            api.get_projects()
            return jsonify({"success": True, "message": "Connection successful"})
        except Exception as e:
            logger.error(f"Error testing Todoist API key: {e}")
            return jsonify(
                {
                    "success": False,
                    "message": "Connection failed. Please check your API key.",
                }
            )

    return bp
