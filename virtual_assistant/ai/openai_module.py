from flask import Blueprint, request, jsonify, render_template
import openai
import os
from dotenv import load_dotenv

# openai_module.py
from virtual_assistant.ai.ai_module import AIInterface
from virtual_assistant.utils.logger import logger


class OpenAIModule(AIInterface):
    def __init__(self):
        load_dotenv()  # take environment variables from .env.
        openai_api_key = os.getenv("OPENAI_API_KEY")
        openai.api_key = openai_api_key
        self.blueprint = Blueprint("openai", __name__, url_prefix="/openai")
        self.blueprint.route("/generate", methods=["POST"])(self.generate_text)
        self.blueprint.route("/ask", methods=["GET"])(self.show_form)

    def generate_text(self):
        try:
            user_input = request.form["user_input"]
            logger.debug(f"User Input: {user_input}")

            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant in charge of my to-do list.",
                    },
                    {"role": "user", "content": user_input},
                ],
            )

            generated_text = response.choices[0].message.content.strip()
            logger.info(
                f"Generated Text: {generated_text}"
            )  # Debugging print statement

            return jsonify({"generated_text": generated_text})

        except Exception as e:
            logger.error(f"Error: {e}")  # Print any exception for debugging
            return jsonify({"error": str(e)}), 500

    # Other OpenAI-specific methods

    def show_form(self):
        return render_template("openai_submit.html")
