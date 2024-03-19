from flask import Blueprint, request, jsonify, render_template_string
import openai
import os
from dotenv import load_dotenv

# openai_module.py
from .ai_module import AIInterface

class OpenAIModule(AIInterface):
    def __init__(self):
        load_dotenv()  # take environment variables from .env.
        openai_api_key = os.getenv('OPENAI_API_KEY')
        openai.api_key = openai_api_key
        self.blueprint = Blueprint('openai', __name__, url_prefix='/openai')
        self.blueprint.route('/generate', methods=['POST'])(self.generate_text)
        self.blueprint.route('/ask', methods=['GET'])(self.show_form)

    def generate_text(self):
        try:
            user_input = request.form['user_input']
            print(f"User Input: {user_input}")  # Debugging print statement


            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant in charge of my to-do list."},
                    {"role": "user", "content": user_input}
                ]
            )

            generated_text = response.choices[0].message.content.strip()
            print(f"Generated Text: {generated_text}")  # Debugging print statement

            return jsonify({'generated_text': generated_text})

        except Exception as e:
            print(f"Error: {e}")  # Print any exception for debugging
            return jsonify({'error': str(e)}), 500

    # Other OpenAI-specific methods

    def show_form(self):
        form_html = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Generate Text</title>
        </head>
        <body>
            <h1>Generate Text with OpenAI</h1>
            <form action="/openai/generate" method="post">
                <label for="user_input">Enter your prompt:</label><br>
                <textarea id="user_input" name="user_input" rows="4" cols="50"></textarea><br>
                <input type="submit" value="Generate">
            </form>
        </body>
        </html>
        '''
        return render_template_string(form_html)


