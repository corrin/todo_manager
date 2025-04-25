from flask import Blueprint, request, jsonify, flash
from flask_login import login_required, current_user
from datetime import datetime, timedelta

from virtual_assistant.utils.logger import logger
from virtual_assistant.database.calendar_account import CalendarAccount
from virtual_assistant.meetings.google_calendar_provider import GoogleCalendarProvider
from virtual_assistant.ai.ai_manager import AIManager
from virtual_assistant.ai.schedule_generator import ScheduleGenerator
from virtual_assistant.meetings.o365_calendar_provider import O365CalendarProvider

def init_schedule_routes():
    bp = Blueprint('schedule', __name__, url_prefix='/api/schedule')
    
    @bp.route('/generate', methods=['POST'])
    @login_required
    def generate_schedule():
        """API endpoint for generating a schedule."""
        try:
            # Get request data
            data = request.get_json() or {}
            custom_instructions = data.get('custom_instructions')
            date_str = data.get('date')
            slot_duration = data.get('slot_duration', current_user.schedule_slot_duration)
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.now().date()
            
            # Generate schedule
            ai_manager = AIManager()
            ai_provider = ai_manager.get_provider(current_user.ai_provider)
            schedule_generator = ScheduleGenerator(ai_provider)
            schedule = schedule_generator.generate_daily_schedule(
                user_id=current_user.id,
                custom_instructions=custom_instructions,
                date=target_date,
                slot_duration=slot_duration
            )
            
            return jsonify(schedule)
            
        except Exception as e:
            logger.error(f"Error generating schedule: {e}")
            flash("An error occurred while generating the schedule.", "danger")
            return jsonify({'error': 'Failed to generate schedule'}), 500
    
    @bp.route('/generate-and-add-to-calendar', methods=['POST'])
    @login_required
    def generate_and_add_to_calendar():
        """Generate a schedule and add it to the user's calendar."""
        try:
            # Get request data
            data = request.get_json() or {}
            custom_instructions = data.get('custom_instructions', current_user.ai_instructions)
            date_str = data.get('date')
            slot_duration = data.get('slot_duration', current_user.schedule_slot_duration)
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.now().date()
            
            # Generate schedule
            ai_manager = AIManager()
            ai_provider = ai_manager.get_provider(current_user.ai_provider)
            schedule_generator = ScheduleGenerator(ai_provider)
            schedule = schedule_generator.generate_daily_schedule(
                user_id=current_user.id,
                custom_instructions=custom_instructions,
                date=target_date,
                slot_duration=slot_duration
            )
            
            # Check if there was an error generating the schedule
            if 'error' in schedule:
                return jsonify(schedule), 500
            
            # Get the user's primary calendar account
            calendar_account = CalendarAccount.query.filter_by(
                user_id=current_user.id,
                is_primary=True
            ).first()
            
            if not calendar_account:
                return jsonify({'error': 'No primary calendar account found. Please set up a calendar in Settings.'}), 400
            
            # Initialize the appropriate calendar provider
            if calendar_account.provider == 'google':
                calendar_provider = GoogleCalendarProvider()
            elif calendar_account.provider == 'o365':
                calendar_provider = O365CalendarProvider()
            else:
                return jsonify({'error': f'Unsupported calendar provider: {calendar_account.provider}'}), 400
            
            # Add each time slot to the calendar
            added_events = []
            for slot in schedule['schedule']:
                # Skip breaks
                if not slot.get('task_id'):
                    continue
                
                # Parse the time slot
                time_str = slot['time']
                times = time_str.split(' - ')
                if len(times) != 2:
                    logger.warning(f"Invalid time format: {time_str}")
                    continue
                
                # Parse start and end times
                try:
                    date_str = schedule['date']
                    start_time = datetime.strptime(f"{date_str} {times[0]}", '%Y-%m-%d %I:%M %p')
                    end_time = datetime.strptime(f"{date_str} {times[1]}", '%Y-%m-%d %I:%M %p')
                except ValueError as e:
                    logger.warning(f"Error parsing time: {e}")
                    continue
                
                # Create meeting details
                meeting_details = {
                    'subject': slot['activity'],
                    'start_time': start_time,
                    'end_time': end_time,
                    'calendar_email': calendar_account.calendar_email,
                    'description': slot.get('notes', ''),
                    'location': ''
                }
                
                try:
                    # Create the event in the calendar
                    event = calendar_provider.create_meeting(meeting_details, current_user.id)
                    added_events.append(event)
                except Exception as e:
                    logger.error(f"Error adding event to calendar: {e}")
                    # Continue with other events even if one fails
            
            # Return the schedule and added events
            return jsonify({
                'schedule': schedule,
                'added_events': added_events
            })
            
        except Exception as e:
            logger.error(f"Error generating schedule and adding to calendar: {e}")
            flash("An error occurred while generating schedule and adding to calendar.", "danger")
            return jsonify({'error': 'Failed to generate schedule and add to calendar'}), 500
    
    return bp