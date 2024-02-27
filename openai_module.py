from flask import Blueprint, request, jsonify, render_template_string
from openai import OpenAI
import os

from dotenv import load_dotenv
load_dotenv()  # take environment variables from .env.


openai_api_key = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=openai_api_key)


openai_blueprint = Blueprint('openai', __name__)

@openai_blueprint.route('/generate', methods=['POST'])
def generate_text():
    try:
        user_input = request.form['user_input']
        print(f"User Input: {user_input}")  # Debugging print statement

        # Set the OpenAI API key

        response = client.chat.completions.create(model="gpt-3.5-turbo",  # Consider using the latest available model
        messages=[
            {"role": "system", "content": "You are a helpful assistant in charge of my to-do list."},
            {"role": "user", "content": user_input}
        ])

        # Accessing the generated text in the response
        generated_text = response.choices[0].message.content.strip()
        print(f"Generated Text: {generated_text}")  # Debugging print statement

        return jsonify({'generated_text': generated_text})
    except Exception as e:
        print(f"Error: {e}")  # Print any exception for debugging
        return jsonify({'error': str(e)}), 500


@openai_blueprint.route('/ask', methods=['GET'])
def show_form():
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
