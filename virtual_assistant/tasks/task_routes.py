from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, session
from virtual_assistant.utils.logger import logger
from virtual_assistant.tasks.task_manager import TaskManager
from virtual_assistant.tasks.task_hierarchy import TaskHierarchy
from virtual_assistant.database.calendar_account import CalendarAccount
from virtual_assistant.database.database import db
import os
import json
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

    @bp.route('/sync')
    def sync_tasks():
        """Sync tasks from all connected task providers."""
        if 'user_email' not in session:
            return redirect(url_for('login'))

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
                tasks = task_manager.get_tasks(task_user_email, provider_name=provider_name)
                
                # Log success
                logger.info(f"Successfully synced {len(tasks)} tasks from {provider_name} for {task_user_email}")
                
                # Add to success results
                success_info = {
                    'email': task_user_email,
                    'provider': provider_name,
                    'tasks_count': len(tasks)
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

    return bp