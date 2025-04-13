from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user

import os
import json
import datetime

from virtual_assistant.utils.logger import logger
from virtual_assistant.tasks.task_manager import TaskManager
from virtual_assistant.tasks.task_hierarchy import TaskHierarchy
from virtual_assistant.database.calendar_account import CalendarAccount
from virtual_assistant.database.database import db
from virtual_assistant.database.task import Task, TaskAccount
from virtual_assistant.tasks.task_provider import Task as ProviderTask

from virtual_assistant.utils.settings import Settings


def init_task_routes():
    bp = Blueprint('tasks', __name__, url_prefix='/tasks')
    task_manager = TaskManager()

    # Refactored get_task_accounts to query TaskAccount table directly
    def get_task_accounts(user_id):
        """Get all active task accounts for a user directly from TaskAccount table.

        Args:
            user_id: The user's database ID.

        Returns:
            List[TaskAccount]: List of active TaskAccount objects for the user.
        """
        # Query TaskAccount table for accounts associated with the user_id
        # Optionally filter further, e.g., only include accounts that are not marked as needing reauth
        # or have necessary credentials (api_key for todoist, token for others)
        active_accounts = TaskAccount.query.filter(
            TaskAccount.user_id == user_id,
            TaskAccount.needs_reauth == False,
            # Add condition to check for credentials presence based on provider type
            db.or_(
                db.and_(TaskAccount.provider_name == 'todoist', TaskAccount.api_key != None),
                db.and_(TaskAccount.provider_name.in_(['google_tasks', 'outlook']), TaskAccount.token != None)
            )
        ).order_by(TaskAccount.provider_name, TaskAccount.task_user_email).all()
        
        logger.debug(f"Found {len(active_accounts)} active task accounts for user_id {user_id}")
        return active_accounts

    @bp.route('/')
    def list_tasks():
        """Display the user's tasks organized into prioritized and unprioritized lists."""
        app_login = session.get('app_login')
        
        try:
            # Try to authenticate with task providers (we'll use Todoist as an example)
            auth_results = task_manager.authenticate(app_login, provider_name='todoist')
            
            # If authentication is needed, redirect to the auth URL
            if 'todoist' in auth_results and auth_results['todoist']:
                provider_name, redirect_url = auth_results['todoist']
                return redirect(redirect_url)
            
            # Get tasks from the database
            
            # Get all tasks for this user
            prioritized_tasks, unprioritized_tasks = Task.get_user_tasks_by_list(app_login)
            
            # If no tasks found in database, sync from providers
            if not prioritized_tasks and not unprioritized_tasks:
                # Redirect to the sync endpoint
                return redirect(url_for('tasks.sync_tasks'))
            
            # Convert database tasks to flattened task format for template
            
            def convert_to_flattened_task(db_task):
                # Convert database task to provider task format
                provider_task = ProviderTask(
                    id=db_task.provider_task_id,
                    title=db_task.title,
                    project_id=db_task.project_id or "",
                    priority=db_task.priority or 2,
                    due_date=db_task.due_date,
                    status=db_task.status,
                    is_instruction=False,
                    parent_id=db_task.parent_id,
                    section_id=db_task.section_id,
                    project_name=db_task.project_name
                )
                
                # Create flattened task dictionary
                return {
                    "task": provider_task,
                    "project": db_task.project_name or "No Project",
                    "path": db_task.title,  # Simplified path for now
                    "flattened_name": f"[{db_task.project_name or 'No Project'}] > {db_task.title}"
                }
            
            # Convert database tasks to flattened tasks for the template
            prioritized_flattened = [convert_to_flattened_task(task) for task in prioritized_tasks]
            unprioritized_flattened = [convert_to_flattened_task(task) for task in unprioritized_tasks]
            
            return render_template('tasks.html', 
                                prioritized_tasks=prioritized_flattened,
                                unprioritized_tasks=unprioritized_flattened)
        
        except Exception as e:
            logger.error(f"Error getting tasks: {e}")
            return render_template('tasks.html', error=str(e))

    @bp.route('/sync')
    def sync_tasks():
        """Sync tasks from all connected and active task providers."""
        user_id = current_user.id
        app_login = current_user.app_login # Keep app_login if needed by other functions called
        
        results = {
            'success': [],
            'errors': [],
            'needs_reauth': [], # Although get_task_accounts filters these, keep for consistency if auth fails later
            'status': 'success',
            'message': ''
        }
        
        # Get all active task accounts for the user using the refactored function
        accounts = get_task_accounts(user_id) # Pass user_id
        
        if not accounts:
            # Handle case where no *active* accounts are found
            message = 'No active task provider accounts found or configured.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': message}), 404
            flash(message, 'warning') # Use warning level
            # Redirect to settings instead of generic error page
            return redirect(url_for('settings'))
        
        # Now 'accounts' is a list of TaskAccount objects
        for account in accounts:
            # Access attributes directly from the TaskAccount object
            provider_name = account.provider_name
            task_user_email = account.task_user_email
            
            logger.info(f"Attempting to sync tasks from {provider_name} for {task_user_email}")
            
            try:
                # Try to authenticate with the provider
                auth_results = task_manager.authenticate(
                    app_login=app_login,
                    task_user_email=task_user_email,
                    provider_name=provider_name
                )
                
                # If authentication is needed, add to needs_reauth
                if provider_name in auth_results and auth_results[provider_name]:
                    provider, redirect_url = auth_results[provider_name]
                    logger.warning(f"⚠️ SKIPPING SYNC: {provider_name} needs authorization for {task_user_email}")
                    results['needs_reauth'].append({
                        'task_user_email': task_user_email, 
                        'provider': provider_name,
                        'reason': 'Authentication required',
                        'reauth_url': redirect_url
                    })
                    results['status'] = 'needs_reauth'
                    continue
                
                # Get tasks from the provider
                try:
                    provider_tasks = task_manager.get_tasks(
                        app_login=app_login,
                        task_user_email=task_user_email,
                        provider_name=provider_name
                    )
                except Exception as e: # Catch any error from get_tasks (incl. provider not found or provider API errors)
                    error_msg = str(e)
                    logger.error(f"Error getting tasks from provider '{provider_name}' for {task_user_email} during sync: {error_msg}")
                    # Add error to results list which is shown to the user
                    results['errors'].append({'task_user_email': task_user_email, 'provider': provider_name, 'error': error_msg}) # Use specific key
                    results['status'] = 'error'
                    continue # Skip this provider on error, try the next one
                
                # Store current provider task IDs to detect deletions
                current_provider_task_ids = [task.id for task in provider_tasks]
                
                # Sync each task with our database
                updated_count = sync_provider_tasks(app_login, task_user_email, provider_name, provider_tasks)
                
                # Log success
                logger.info(f"Successfully synced {updated_count} tasks from {provider_name} for {task_user_email}")
                
                # Add to success results
                success_info = {
                    'task_user_email': task_user_email, # Use specific key
                    'provider': provider_name,
                    'tasks_count': updated_count
                }
                results['success'].append(success_info)
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ ERROR: Error syncing {provider_name} tasks for {task_user_email}: {error_msg}")
                results['errors'].append({
                    'task_user_email': task_user_email, # Use specific key
                    'provider': provider_name,
                    'error': error_msg
                })
                results['status'] = 'error'
        
        # Set overall status message
        if results['needs_reauth']:
            reauth_details = [f"{a['provider']} - {a.get('reason', 'Unknown reason')}" 
                            for a in results['needs_reauth']]
            results['message'] = f"Some providers need authorization:\n" + "\n".join(reauth_details)
            
        elif not results['success'] and results['errors']:
            results['message'] = 'All task syncs failed'
            
        elif results['errors']:
            results['message'] = 'Some task syncs failed'
            
        else:
            results['message'] = 'All tasks synced successfully'

        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(results)

        # For success cases, show task sync results page
        return render_template(
            'task_sync_results.html',
            sync_results=results,
            title="Task Sync Results"
        )

    @bp.route('/update_order', methods=['POST'])
    def update_task_order():
        """Update task order based on drag-and-drop reordering."""
        app_login = session.get('app_login')
        
        try:
            # Get the new task order from the request
            task_order_json = request.form.get('order')
            if not task_order_json:
                return jsonify({'error': 'No task order provided'}), 400
                
            task_order = json.loads(task_order_json)
            
            # Get the list type (prioritized or unprioritized)
            list_type = request.form.get('list_type', 'prioritized')
            
            # Convert the task order array to a dict of task_id -> position
            task_positions = {item['id']: item['position'] for item in task_order}
            
            # Update the task order in the database
            Task.update_task_order(app_login, list_type, task_positions)
            
            logger.info(f"Updated {list_type} task order for {app_login}, {len(task_order)} tasks")
            
            return jsonify({
                'success': True,
                'message': f'{list_type.capitalize()} task order updated successfully'
            })
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error updating task order: {error_msg}")
            return jsonify({'error': error_msg}), 500

    @bp.route('/move_task', methods=['POST'])
    def move_task_between_lists():
        """Move a task between prioritized and unprioritized lists."""
        app_login = session.get('app_login')
        
        try:
            # Get task ID and destination list
            task_id = request.form.get('task_id')
            destination = request.form.get('destination')
            position = request.form.get('position')
            
            if not task_id or not destination or destination not in ['prioritized', 'unprioritized']:
                return jsonify({'error': 'Invalid parameters'}), 400
            
            # Convert position to integer if provided
            if position is not None:
                position = int(position)
                
            # Find the task in our database
            task = Task.query.filter_by(
                app_login=app_login,
                provider_task_id=task_id
            ).first()
            
            if not task:
                return jsonify({'error': 'Task not found'}), 404
                
            # Move the task in the database
            Task.move_task(task.id, destination, position)
            
            logger.info(f"Moved task {task_id} to {destination} list for {app_login}")
            
            return jsonify({
                'success': True,
                'message': f'Task moved to {destination} list successfully'
            })
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error moving task between lists: {error_msg}")
            return jsonify({'error': error_msg}), 500

    @bp.route('/get_task_lists', methods=['GET'])
    def get_task_lists():
        """Get the prioritized and unprioritized task lists."""
        app_login = session.get('app_login')
        
        # Get tasks from database
        prioritized, unprioritized = Task.get_user_tasks_by_list(app_login)
        
        # Convert to dictionaries
        result = {
            'prioritized': [{'id': task.provider_task_id, 'position': task.position} for task in prioritized],
            'unprioritized': [{'id': task.provider_task_id, 'position': task.position} for task in unprioritized]
        }
        
        return jsonify(result)

    @bp.route('/<task_id>/details', methods=['GET'])
    def get_task_details(task_id):
        """Get detailed information for a specific task."""
        # app_login = session.get('app_login') # Use current_user instead
        user_id = current_user.id
        
        # Try to find the task in our database
        task = Task.query.filter_by(
            user_id=user_id, # Use user_id
            provider_task_id=task_id
        ).first()
        
        if task:
            # Return task details if found locally
            return jsonify(task.to_dict())
        else:
            # If not found in local DB (populated by sync), return 404
            logger.warning(f"Task details requested but not found locally for task_id {task_id}, user_id {user_id}")
            return jsonify({'error': 'Task not found'}), 404

    @bp.route('/<task_id>/update_status', methods=['POST'])
    def update_task_status(task_id):
        """Update a task's status (complete/incomplete)."""
        app_login = session['app_login']
        
        # Get the new status from the form
        new_status = request.form.get('status', 'active')
        logger.info(f"Task status update request: task_id={task_id}, new_status='{new_status}', user={app_login}")
        
        # Get the task from the database by provider_task_id
        task = Task.query.filter_by(provider_task_id=task_id, app_login=app_login).first()
        
        if not task:
            error_message = f"Task not found for task_id={task_id}"
            logger.warning(f"{error_message} for user={app_login}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': error_message}), 404
            flash(error_message, 'danger')
            return redirect(url_for('tasks.list_tasks'))
        
        # Log the current task status with both IDs for clarity
        logger.info(f"Found task in database: task_id={task_id} (maps to database_id={task.id}), provider={task.provider}, status='{task.status}'")
        
        # Check if the status is already set to the requested value
        if task.status == new_status:
            message = f"Task '{task.title}' is already marked as {new_status}"
            logger.info(f"{message} (task_id={task_id})")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'message': message, 'status': 'unchanged'}), 200
            flash(message, 'info')
            return redirect(url_for('tasks.list_tasks'))
        
        # Create the task manager
        task_manager = TaskManager()
        
        try:
            # Get the appropriate provider
            # Get the provider instance (no longer need app_login here)
            provider = task_manager.get_provider(task.provider)
            if not provider:
                error_message = f"Provider '{task.provider}' not available or configured."
                logger.error(f"{error_message} for task_id={task_id} (db_id={task.id})")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': error_message}), 500
                flash(error_message, 'danger')
                return redirect(url_for('tasks.list_tasks')) # Redirect to list_tasks

            # Determine the correct email identifier for the provider API call.
            # Assumes task.task_user_email is correctly populated for Google/Outlook during sync.
            task_email_to_use = task.task_user_email if task.provider in ['google_tasks', 'outlook'] else app_login

            # If email is missing for a provider that requires it, raise an error.
            if not task_email_to_use and task.provider in ['google_tasks', 'outlook']:
                error_message = f"Cannot update task: Missing identifying email for provider '{task.provider}' and task ID {task_id}. Please re-sync tasks."
                logger.error(error_message)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': error_message}), 500
                flash(error_message, 'danger')
                return redirect(url_for('tasks.list_tasks'))
            
            # Update the task status in the provider
            logger.info(f"Updating task status in provider: task_id={task_id} (provider_id={task.provider_task_id}), provider={task.provider}, task_user_email='{task_email_to_use}', old_status='{task.status}', new_status='{new_status}'")
            
            # Call provider method with the correct email
            provider.update_task_status(
                task_user_email=task_email_to_use,
                task_id=task.provider_task_id,
                status=new_status
            )
            
            # If we get here, the provider update was successful, so update our database
            old_status = task.status
            task.status = new_status
            task.last_synced = datetime.datetime.utcnow()
            db.session.commit()
            
            logger.info(f"Successfully updated task status: task_id={task_id}, provider={task.provider}, status changed from '{old_status}' to '{new_status}'")
            
            # Return success
            success_message = f"Task '{task.title}' marked as {new_status}"
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'message': success_message, 'status': 'success'}), 200
            flash(success_message, 'success')
            return redirect(url_for('tasks.list_tasks'))
            
        except Exception as e:
            error_message = f"Error updating task status: {str(e)}"
            logger.error(f"{error_message} - task_id={task_id}, provider={task.provider}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': error_message}), 500
            flash(error_message, 'danger')
            return redirect(url_for('tasks.list_tasks'))

    # Removed redundant update_task_status_direct and sync_todoist routes.
    @bp.route('/set_primary_task_provider', methods=['POST'])
    @login_required
    def set_primary_task_provider():
        """Sets the primary task provider account via AJAX."""
        account_id_str = request.form.get('primary_task_account_id')
        user_id = current_user.id

        if not account_id_str:
            logger.warning(f"User {user_id} - Set primary task provider: No account ID received.")
            return jsonify({'success': False, 'message': 'No provider account ID received.'}), 400

        try:
            account_id = int(account_id_str)

            db.session.begin_nested()
            # Ensure only one primary: Reset flag for all user's task accounts first
            TaskAccount.query.filter_by(user_id=user_id).update({'is_primary': False})
            # Set the selected account as primary
            updated_count = TaskAccount.query.filter_by(id=account_id, user_id=user_id).update({'is_primary': True})

            if updated_count == 1:
                db.session.commit()
                logger.info(f"User {user_id} - Set primary task provider: Account ID {account_id}")
                return jsonify({'success': True, 'message': 'Primary task provider updated.'})
            else:
                # Account not found for this user
                db.session.rollback()
                logger.error(f"User {user_id} - Set primary task provider: Failed to find TaskAccount ID {account_id}.")
                return jsonify({'success': False, 'message': 'Selected task account not found.'}), 404

        except Exception as e:
            # Catch any error during parsing or database operations
            db.session.rollback()
            logger.exception(
                f"User {user_id} - Set primary task provider: Error processing account_id '{account_id_str}': {e}"
            )
            # Return a generic error message for all failure types
            return jsonify({'success': False, 'message': 'An error occurred while setting the primary task provider.'}), 500

    @bp.route('/delete_task_account', methods=['POST'])
    @login_required
    def delete_task_account():
        """Deletes a specific task provider account for the user."""
        account_id_str = request.form.get('account_id')
        user_id = current_user.id
        
        if not account_id_str:
            flash('Invalid request: Account ID missing.', 'danger')
            return redirect(url_for('settings'))
            
        try:
            account_id = int(account_id_str)
            
            # Find the task account to be deleted
            account_to_delete = TaskAccount.query.filter_by(id=account_id, user_id=user_id).first()
            
            if not account_to_delete:
                flash('Task account not found or you do not have permission to delete it.', 'warning')
                return redirect(url_for('settings'))
                
            provider_name = account_to_delete.provider_name # For logging/flash message
            email = account_to_delete.task_user_email
            
            # Check if deleting the primary task provider
            was_primary = account_to_delete.is_primary
            
            # Delete the account
            db.session.delete(account_to_delete)
            db.session.commit()
            
            logger.info(f"User {user_id} deleted TaskAccount ID {account_id} ({provider_name} - {email})")
            flash(f"Successfully deleted {provider_name} task account for {email}.", 'success')
            
            # If the deleted account was primary, log it. We are not auto-assigning a new primary for tasks.
            if was_primary:
                 logger.info(f"Deleted task account {account_id} was the primary task provider for user {user_id}.")
                 
        except ValueError:
            flash('Invalid Account ID format.', 'danger')
            logger.error(f"User {user_id} - Delete task account: Invalid account ID format '{account_id_str}'")
        except Exception as e:
            db.session.rollback()
            logger.exception(f"User {user_id} - Delete task account: Error deleting account ID {account_id_str}: {e}")
            flash('An error occurred while deleting the task account.', 'danger')
            
        return redirect(url_for('settings'))

    return bp
def sync_provider_tasks(app_login, task_user_email, provider_name, provider_tasks):
    """Sync tasks from a provider to the database.
    
    Args:
        app_login: The user's login identifier for this application
        task_user_email: The email associated with the task provider account
        provider_name: The name of the provider (e.g., 'todoist')
        provider_tasks: List of tasks from the provider
        
    Returns:
        int: Number of tasks updated
    """
    
    logger.info(f"Starting sync of {len(provider_tasks)} tasks from {provider_name} for app_login={app_login}, task_user_email={task_user_email}")
    
    # Log task statuses from provider
    task_statuses = {}
    for task in provider_tasks:
        task_statuses[task.id] = task.status
        if task.status == 'completed':
            logger.debug(f"Provider task {task.id} is marked as completed")
        elif task.status == 'active':
            logger.debug(f"Provider task {task.id} is marked as active/incomplete")
    
    logger.debug(f"Task statuses from {provider_name}: {task_statuses}")
    
    updated_count = 0
    created_count = 0
    unchanged_count = 0
    status_change_count = 0
    
    # For each task from the provider
    for provider_task in provider_tasks:
        # Create or update the task in the database
        before_status = None
        
        # Check if task exists to log status changes
        existing_task = Task.query.filter_by(
            app_login=app_login,
            provider=provider_name,
            provider_task_id=provider_task.id
        ).first()
        
        if existing_task:
            before_status = existing_task.status
            logger.debug(f"Before sync: Task {provider_task.id} status in DB: '{before_status}', in provider: '{provider_task.status}'")
        
        # Create or update the task
        task, created_or_updated = Task.create_or_update_from_provider_task(
            app_login=app_login,
            task_user_email=task_user_email,
            provider=provider_name,
            provider_task=provider_task
        )
        
        if created_or_updated:
            if existing_task:
                updated_count += 1
                # Check if status specifically changed
                if before_status != task.status:
                    status_change_count += 1
                    logger.info(f"Task status changed during sync: {provider_task.id} from '{before_status}' to '{task.status}'")
            else:
                created_count += 1
        else:
            unchanged_count += 1
    
    # Clean up deleted tasks
    current_provider_task_ids = [task.id for task in provider_tasks]
    deleted_count = Task.sync_task_deletions(app_login, provider_name, current_provider_task_ids)
    
    # Log summary
    logger.info(f"Sync summary for {provider_name}: Created {created_count}, Updated {updated_count} (Status changes: {status_change_count}), Unchanged {unchanged_count}, Deleted {deleted_count}")
    
    return updated_count + created_count