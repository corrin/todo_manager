from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, session

import os
import json
import datetime

from virtual_assistant.utils.logger import logger
from virtual_assistant.tasks.task_manager import TaskManager
from virtual_assistant.tasks.task_hierarchy import TaskHierarchy
from virtual_assistant.database.calendar_account import CalendarAccount
from virtual_assistant.database.database import db
from virtual_assistant.database.task import Task
from virtual_assistant.tasks.task_provider import Task as ProviderTask

from virtual_assistant.utils.settings import Settings


def init_task_routes():
    bp = Blueprint('tasks', __name__, url_prefix='/tasks')
    task_manager = TaskManager()

    def get_task_accounts(app_user_email):
        """Get all task accounts for a user.
        
        Args:
            app_user_email: The email the user uses to access the app
            
        Returns:
            List of dicts with provider and task_user_email
        """
        accounts = []
        
        # Get all available task providers
        available_providers = task_manager.get_available_providers()
        
        # Map calendar providers to task providers
        calendar_to_task_map = {
            'google': 'google_tasks',
            'o365': 'outlook'
        }
        
        # For calendar-based task providers (Outlook, Google Tasks)
        # Get all calendar accounts for this user
        calendar_accounts = CalendarAccount.get_accounts_for_user(app_user_email)
        
        for calendar_account in calendar_accounts:
            calendar_provider = calendar_account.provider
            if calendar_provider in calendar_to_task_map:
                task_provider = calendar_to_task_map[calendar_provider]
                
                # Only add if the task provider is available
                if task_provider in available_providers:
                    accounts.append({
                        'provider': task_provider,
                        'task_user_email': calendar_account.calendar_email
                    })
        
        # For Todoist, there's typically just one account per user
        if 'todoist' in available_providers:
            provider = task_manager.get_provider('todoist')
            credentials = provider.get_credentials(app_user_email)
            if credentials:
                accounts.append({
                    'provider': 'todoist',
                    'task_user_email': app_user_email  # Todoist uses the app user's email
                })
                
        # For SQLite, there's typically just one account per user
        if 'sqlite' in available_providers:
            accounts.append({
                'provider': 'sqlite',
                'task_user_email': app_user_email  # SQLite uses the app user's email
            })
        
        return accounts

    @bp.route('/')
    def list_tasks():
        """Display the user's tasks organized into prioritized and unprioritized lists."""
        user_email = session.get('user_email')
        
        try:
            # Try to authenticate with task providers (we'll use Todoist as an example)
            auth_results = task_manager.authenticate(user_email, provider_name='todoist')
            
            # If authentication is needed, redirect to the auth URL
            if 'todoist' in auth_results and auth_results['todoist']:
                provider_name, redirect_url = auth_results['todoist']
                return redirect(redirect_url)
            
            # Get tasks from the database
            
            # Get all tasks for this user
            prioritized_tasks, unprioritized_tasks = Task.get_user_tasks_by_list(user_email)
            
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
        """Sync tasks from all connected task providers."""
        app_user_email = session.get('user_email')
        
        results = {
            'success': [],
            'errors': [],
            'needs_reauth': [],
            'status': 'success',
            'message': ''
        }
        
        # Get all task accounts for the user
        accounts = get_task_accounts(app_user_email)
        
        if not accounts:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'No task accounts found'}), 404
            flash('No task accounts found', 'error')
            return render_template("error.html", error="No task accounts found", title="No Accounts")
        
        for account in accounts:
            provider_name = account['provider']
            task_user_email = account['task_user_email']
            
            logger.info(f"Attempting to sync tasks from {provider_name} for {task_user_email}")
            
            try:
                # Try to authenticate with the provider
                auth_results = task_manager.authenticate(task_user_email, provider_name=provider_name)
                
                # If authentication is needed, add to needs_reauth
                if provider_name in auth_results and auth_results[provider_name]:
                    provider, redirect_url = auth_results[provider_name]
                    logger.warning(f"⚠️ SKIPPING SYNC: {provider_name} needs authorization for {task_user_email}")
                    results['needs_reauth'].append({
                        'email': task_user_email,
                        'provider': provider_name,
                        'reason': 'Authentication required',
                        'reauth_url': redirect_url
                    })
                    results['status'] = 'needs_reauth'
                    continue
                
                # Get tasks from the provider
                provider_tasks = task_manager.get_tasks(task_user_email, provider_name=provider_name)
                
                # Store current provider task IDs to detect deletions
                current_provider_task_ids = [task.id for task in provider_tasks]
                
                # Sync each task with our database
                updated_count = sync_provider_tasks(task_user_email, provider_name, provider_tasks)
                
                # Log success
                logger.info(f"Successfully synced {updated_count} tasks from {provider_name} for {task_user_email}")
                
                # Add to success results
                success_info = {
                    'email': task_user_email,
                    'provider': provider_name,
                    'tasks_count': updated_count
                }
                results['success'].append(success_info)
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ ERROR: Error syncing {provider_name} tasks for {task_user_email}: {error_msg}")
                results['errors'].append({
                    'email': task_user_email,
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
        app_user_email = session.get('user_email')
        
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
            Task.update_task_order(app_user_email, list_type, task_positions)
            
            logger.info(f"Updated {list_type} task order for {app_user_email}, {len(task_order)} tasks")
            
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
        app_user_email = session.get('user_email')
        
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
                user_email=app_user_email, 
                provider_task_id=task_id
            ).first()
            
            if not task:
                return jsonify({'error': 'Task not found'}), 404
                
            # Move the task in the database
            Task.move_task(task.id, destination, position)
            
            logger.info(f"Moved task {task_id} to {destination} list for {app_user_email}")
            
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
        app_user_email = session.get('user_email')
        
        # Get tasks from database
        prioritized, unprioritized = Task.get_user_tasks_by_list(app_user_email)
        
        # Convert to dictionaries
        result = {
            'prioritized': [{'id': task.provider_task_id, 'position': task.position} for task in prioritized],
            'unprioritized': [{'id': task.provider_task_id, 'position': task.position} for task in unprioritized]
        }
        
        return jsonify(result)

    @bp.route('/<task_id>/details', methods=['GET'])
    def get_task_details(task_id):
        """Get detailed information for a specific task."""
        app_user_email = session.get('user_email')
        
        # Try to find the task in our database
        task = Task.query.filter_by(
            user_email=app_user_email,
            provider_task_id=task_id
        ).first()
        
        if task:
            # Return task details from our database
            return jsonify(task.to_dict())
            
        # If not found in our database, fallback to searching providers
        accounts = get_task_accounts(app_user_email)
        
        if not accounts:
            return jsonify({'error': 'No task accounts found'}), 404
        
        # Look for the task in all accounts
        task_details = None
        
        for account in accounts:
            provider_name = account['provider']
            task_user_email = account['task_user_email']
            
            try:
                # Try to authenticate with the provider
                auth_results = task_manager.authenticate(task_user_email, provider_name=provider_name)
                
                # Skip this provider if authentication is needed
                if provider_name in auth_results and auth_results[provider_name]:
                    continue
                
                # Get all tasks from this provider
                tasks = task_manager.get_tasks(task_user_email, provider_name=provider_name)
                
                # Look for the task by ID
                for provider_task in tasks:
                    if provider_task.id == task_id:
                        # Found the task, create a detailed response
                        task_details = {
                            'id': provider_task.id,
                            'provider': provider_name,
                            'provider_task_id': provider_task.id,
                            'title': provider_task.title,
                            'status': provider_task.status,
                            'due_date': provider_task.due_date.isoformat() if provider_task.due_date else None,
                            'priority': provider_task.priority,
                            'project_id': provider_task.project_id,
                            'project_name': getattr(provider_task, 'project_name', None) or '',
                            'parent_id': getattr(provider_task, 'parent_id', None),
                            'section_id': getattr(provider_task, 'section_id', None),
                        }
                        
                        # Create or update this task in our database for future requests
                        db_task, _ = Task.create_or_update_from_provider_task(
                            app_user_email, 
                            provider_name, 
                            provider_task
                        )
                        
                        # Use the database task's list type and position
                        task_details['list_type'] = db_task.list_type
                        task_details['position'] = db_task.position
                        
                        break
                
                # If we found the task, no need to check other providers
                if task_details:
                    break
                    
            except Exception as e:
                logger.error(f"Error getting task details from {provider_name}: {e}")
                continue
        
        if task_details:
            return jsonify(task_details)
        else:
            return jsonify({'error': 'Task not found'}), 404

    @bp.route('/<task_id>/update_status', methods=['POST'])
    def update_task_status(task_id):
        """Update a task's status (complete/incomplete)."""
        user_email = session['user_email']
        
        # Get the new status from the form
        new_status = request.form.get('status', 'active')
        logger.info(f"Task status update request: task_id={task_id}, new_status='{new_status}', user={user_email}")
        
        # Get the task from the database by provider_task_id
        task = Task.query.filter_by(provider_task_id=task_id, user_email=user_email).first()
        
        if not task:
            error_message = f"Task not found for task_id={task_id}"
            logger.warning(f"{error_message} for user={user_email}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': error_message}), 404
            flash(error_message, 'danger')
            return redirect(url_for('tasks'))
        
        # Log the current task status with both IDs for clarity
        logger.info(f"Found task in database: task_id={task_id} (maps to database_id={task.id}), provider={task.provider}, status='{task.status}'")
        
        # Check if the status is already set to the requested value
        if task.status == new_status:
            message = f"Task '{task.title}' is already marked as {new_status}"
            logger.info(f"{message} (task_id={task_id})")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'message': message, 'status': 'unchanged'}), 200
            flash(message, 'info')
            return redirect(url_for('tasks'))
        
        # Create the task manager
        task_manager = TaskManager()
        
        try:
            # Get the appropriate provider
            provider = task_manager.get_provider(task.provider, user_email)
            if not provider:
                error_message = f"Provider {task.provider} not available"
                logger.error(f"{error_message} for task_id={task_id}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': error_message}), 500
                flash(error_message, 'danger')
                return redirect(url_for('tasks'))
            
            # Update the task status in the provider
            logger.info(f"Updating task status in provider: task_id={task_id}, provider={task.provider}, old_status='{task.status}', new_status='{new_status}'")
            provider.update_task_status(task_id=task.provider_task_id, status=new_status)
            
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
            return redirect(url_for('tasks'))
            
        except Exception as e:
            error_message = f"Error updating task status: {str(e)}"
            logger.error(f"{error_message} - task_id={task_id}, provider={task.provider}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': error_message}), 500
            flash(error_message, 'danger')
            return redirect(url_for('tasks'))

    @bp.route('/<task_id>/status', methods=['POST'])
    def update_task_status_direct(task_id):
        """Update a task's status (completed/active)."""
        user_email = session.get('user_email')
        status = request.form.get('status')
        
        if not status:
            flash('Status is required', 'danger')
            return redirect(url_for('tasks'))
        
        # Look up provider and provider_task_id
        task = Task.query.filter_by(provider_task_id=task_id, user_email=user_email).first()
        
        if task:
            provider = task.provider
            provider_task_id = task.provider_task_id
        else:
            provider = 'todoist'  # Default provider if task not found in database
            provider_task_id = task_id
        
        logger.info(f"update task status: task_id={task_id}, status={status}, user={user_email}, provider={provider}, provider_task_id={provider_task_id}")
        
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        try:
            task_manager.update_task_status(user_email, task_id, status, provider_name='todoist')
            
            if is_ajax:
                return jsonify({'success': True, 'message': f'Task status updated to {status}'})
            else:
                flash(f'Task status updated to {status}', 'success')
                return redirect(url_for('tasks'))
                
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error updating task status: task_id={task_id}, provider={provider}, provider_task_id={provider_task_id}, error={error_message}")
            
            if is_ajax:
                return jsonify({'success': False, 'message': error_message}), 400
            else:
                flash(f'Error updating task status: {error_message}', 'danger')
                return redirect(url_for('tasks'))

    @bp.route('/sync_todoist')
    def sync_todoist():
        """Sync Todoist tasks."""
        user_email = session.get('user_email')
        
        try:
            # Try to authenticate with Todoist
            auth_results = task_manager.authenticate(user_email, provider_name='todoist')
            
            # If authentication is needed, redirect to the auth URL
            if 'todoist' in auth_results and auth_results['todoist']:
                provider_name, redirect_url = auth_results['todoist']
                return redirect(redirect_url)
            
            # Get tasks from Todoist to refresh the cache
            tasks = task_manager.get_tasks(user_email, provider_name='todoist')
            
            # Create a task hierarchy to get a better count of tasks
            hierarchy = TaskHierarchy(tasks)
            flattened_tasks = hierarchy.get_flattened_tasks()
            
            flash(f'Successfully synced {len(tasks)} Todoist tasks', 'success')
            logger.info(f"Successfully synced {len(tasks)} Todoist tasks for {user_email}")
            
            # Redirect to the tasks page to show the synced tasks
            return redirect(url_for('tasks'))
        
        except Exception as e:
            logger.error(f"Error syncing Todoist tasks: {e}")
            flash(f'Error syncing Todoist tasks: {str(e)}', 'error')
            return redirect(url_for('tasks'))

    return bp

def sync_provider_tasks(user_email, provider_name, provider_tasks):
    """Sync tasks from a provider to the database.
    
    Args:
        user_email: The user's email
        provider_name: The name of the provider (e.g., 'todoist')
        provider_tasks: List of tasks from the provider
        
    Returns:
        int: Number of tasks updated
    """
    
    logger.info(f"Starting sync of {len(provider_tasks)} tasks from {provider_name} for {user_email}")
    
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
            user_email=user_email,
            provider=provider_name,
            provider_task_id=provider_task.id
        ).first()
        
        if existing_task:
            before_status = existing_task.status
            logger.debug(f"Before sync: Task {provider_task.id} status in DB: '{before_status}', in provider: '{provider_task.status}'")
        
        # Create or update the task
        task, created_or_updated = Task.create_or_update_from_provider_task(
            user_email=user_email,
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
    deleted_count = Task.sync_task_deletions(user_email, provider_name, current_provider_task_ids)
    
    # Log summary
    logger.info(f"Sync summary for {provider_name}: Created {created_count}, Updated {updated_count} (Status changes: {status_change_count}), Unchanged {unchanged_count}, Deleted {deleted_count}")
    
    return updated_count + created_count