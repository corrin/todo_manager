from virtual_assistant.ai.ai_provider import AIProvider
from virtual_assistant.database.task import Task
from virtual_assistant.utils.logger import logger
from datetime import datetime, timedelta
import json

# TODO: TEMPORARY DEBUG LOGGING
# The detailed debug logging in this file is temporary for development purposes.
# Once the schedule generation feature is working properly, these debug logs should be removed.

class ScheduleGenerator:
    """Generate daily schedules based on prioritized tasks and custom instructions."""
    
    def __init__(self, ai_provider: AIProvider):
        """Initialize with an AI provider instance."""
        self.ai_provider = ai_provider
    
    def generate_daily_schedule(self, user_id, custom_instructions=None, date=None, slot_duration=60):
        """
        Generate a daily schedule based on prioritized tasks and custom instructions.
        
        Args:
            user_id: The user's database ID
            custom_instructions: Custom scheduling instructions (e.g., "Schedule 4 hours of MSM weekly")
            date: The date to generate the schedule for (defaults to today)
            slot_duration: Duration of each time slot in minutes (30, 60, or 120)
            
        Returns:
            dict: The generated schedule
        """
        logger.debug(f"[DEBUG] Starting schedule generation for user_id={user_id}")
        logger.debug(f"[DEBUG] Custom instructions: {custom_instructions}")
        logger.debug(f"[DEBUG] Date: {date}, Slot duration: {slot_duration}")
        
        # Get the date to generate schedule for
        target_date = date or datetime.now().date()
        logger.debug(f"[DEBUG] Target date: {target_date}")
        
        # Get prioritized tasks
        logger.debug(f"[DEBUG] Fetching prioritized tasks for user_id={user_id}")
        prioritized_tasks, _, _ = Task.get_user_tasks_by_list(user_id)
        logger.debug(f"[DEBUG] Found {len(prioritized_tasks)} prioritized tasks")
        
        # Format tasks for the AI prompt
        task_list = []
        for task in prioritized_tasks:
            task_info = {
                "id": str(task.id),
                "title": task.title,
                "project": task.project_name or "No Project",
                "priority": task.priority or 2,
                "due_date": task.due_date.isoformat() if task.due_date else None
            }
            task_list.append(task_info)
        
        # Create the prompt for the AI
        logger.debug(f"[DEBUG] Creating AI prompt with {len(task_list)} tasks")
        prompt = self._create_schedule_prompt(task_list, custom_instructions, target_date, slot_duration)
        logger.debug(f"[DEBUG] AI prompt created (length: {len(prompt)} chars)")
        
        try:
            # Generate the schedule using the AI provider
            logger.debug(f"[DEBUG] Sending prompt to AI provider (type: {type(self.ai_provider).__name__})")
            response = self.ai_provider.generate_text(user_id, prompt)
            logger.debug(f"[DEBUG] Received response from AI provider (length: {len(response)} chars)")
            
            # Parse the response
            logger.debug(f"[DEBUG] Parsing AI response")
            schedule = self._parse_schedule_response(response)
            logger.debug(f"[DEBUG] Schedule parsed successfully: {json.dumps(schedule, indent=2)[:200]}...")
            return schedule
        except Exception as e:
            logger.error(f"Error generating schedule: {e}")
            logger.debug(f"[DEBUG] Exception details: {type(e).__name__}: {str(e)}")
            raise
    
    def _create_schedule_prompt(self, tasks, custom_instructions, target_date, slot_duration=60):
        """Create a prompt for the AI to generate a schedule."""
        logger.debug(f"[DEBUG] Creating schedule prompt for date: {target_date}")
        logger.debug(f"[DEBUG] Number of tasks: {len(tasks)}")
        logger.debug(f"[DEBUG] Custom instructions provided: {bool(custom_instructions)}")
        logger.debug(f"[DEBUG] Slot duration: {slot_duration} minutes")
        
        date_str = target_date.strftime("%A, %B %d, %Y")
        logger.debug(f"[DEBUG] Formatted date string: {date_str}")
        
        # Base prompt
        prompt = f"""
        I need to create a daily schedule for {date_str}.
        
        Here are my prioritized tasks:
        {json.dumps(tasks, indent=2)}
        
        """
        
        # Add custom instructions if provided
        if custom_instructions:
            logger.debug(f"[DEBUG] Adding custom instructions to prompt")
            prompt += f"""
            Please consider these scheduling preferences:
            {custom_instructions}
            """
        
        # Add slot duration information
        prompt += f"""
        Please create time slots with a duration of {slot_duration} minutes each.
        """
        
        # Add specific instructions for the AI
        logger.debug(f"[DEBUG] Adding standard scheduling instructions")
        prompt += """
        Based on the tasks and preferences, please create a detailed hour-by-hour schedule for the day.
        The schedule should:
        1. Allocate appropriate time for each task based on its priority and due date
        2. Include breaks and lunch
        3. Follow any custom scheduling preferences provided
        4. Be realistic about what can be accomplished in a day
        5. Start at 9:00 AM and end by 5:00 PM
        
        Format your response as a JSON object with the following structure:
        {
          "date": "YYYY-MM-DD",
          "schedule": [
            {
              "time": "HH:MM AM/PM - HH:MM AM/PM",
              "activity": "Task description or break",
              "task_id": "task_id or null for breaks",
              "notes": "Optional notes about this time slot"
            },
            ...
          ]
        }
        """
        
        logger.debug(f"[DEBUG] Prompt created, total length: {len(prompt)} characters")
        return prompt
    
    def _parse_schedule_response(self, response):
        """Parse the AI response into a structured schedule."""
        logger.debug(f"[DEBUG] Starting to parse schedule response")
        logger.debug(f"[DEBUG] Response first 100 chars: {response[:100]}...")
        
        try:
            # Try to extract JSON from the response
            # First, look for JSON within triple backticks
            import re
            logger.debug(f"[DEBUG] Looking for JSON in triple backticks")
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
            
            if json_match:
                json_str = json_match.group(1)
                logger.debug(f"[DEBUG] Found JSON in triple backticks")
            else:
                # If no triple backticks, try to find JSON object directly
                logger.debug(f"[DEBUG] Looking for JSON object directly")
                json_match = re.search(r'(\{[\s\S]*\})', response)
                if json_match:
                    json_str = json_match.group(1)
                    logger.debug(f"[DEBUG] Found JSON object directly")
                else:
                    # If still no JSON found, use the entire response
                    logger.debug(f"[DEBUG] No JSON format found, using entire response")
                    json_str = response
            
            logger.debug(f"[DEBUG] Extracted JSON string first 100 chars: {json_str[:100]}...")
            
            # Parse the JSON
            logger.debug(f"[DEBUG] Attempting to parse JSON")
            schedule = json.loads(json_str)
            logger.debug(f"[DEBUG] JSON parsed successfully")
            
            # Validate the schedule structure
            logger.debug(f"[DEBUG] Validating schedule structure")
            if not isinstance(schedule, dict):
                logger.debug(f"[DEBUG] Validation failed: Schedule is not a dictionary")
                raise ValueError("Schedule is not a dictionary")
            
            if "date" not in schedule or "schedule" not in schedule:
                logger.debug(f"[DEBUG] Validation failed: Schedule missing required fields")
                raise ValueError("Schedule missing required fields")
            
            if not isinstance(schedule["schedule"], list):
                logger.debug(f"[DEBUG] Validation failed: Schedule entries is not a list")
                raise ValueError("Schedule entries is not a list")
            
            logger.debug(f"[DEBUG] Schedule validation passed")
            logger.debug(f"[DEBUG] Schedule date: {schedule['date']}, entries: {len(schedule['schedule'])}")
            
            # Return the parsed schedule
            return schedule
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse schedule JSON: {e}")
            logger.debug(f"[DEBUG] JSON decode error: {str(e)}")
            logger.debug(f"[DEBUG] JSON string that failed to parse: {json_str[:200]}...")
            # Return a formatted error response
            return {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "error": "Failed to parse AI response",
                "raw_response": response
            }
        except Exception as e:
            logger.error(f"Error parsing schedule response: {e}")
            logger.debug(f"[DEBUG] Exception details: {type(e).__name__}: {str(e)}")
            # Return a formatted error response
            return {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "error": str(e),
                "raw_response": response
            }