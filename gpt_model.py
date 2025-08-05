import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure the Gemini API client
# The API key should be stored in your .env file as GEMINI_API_KEY
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set. Please set it in your .env file.")

genai.configure(api_key=GEMINI_API_KEY)

# Define the model to use for general chat
# Using a flash model for faster responses and lower memory footprint
GEMINI_MODEL_NAME = "gemini-2.5-flash-preview-05-20"

# --- General User Chat Response ---
def get_gpt_response(user_input, my_info, chat_history, lang="en"):
    """
    Generates a response from the Gemini model for a regular user.
    It uses the provided chat history to maintain context.
    """
    try:
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        
        # Prepare the chat history for the model
        # The chat_history from Flask session needs to be converted
        # to the format expected by the Gemini API
        formatted_history = []
        for message in chat_history:
            # Ensure 'parts' is a list of dictionaries with 'text' key
            if isinstance(message.get('parts'), list) and message['parts']:
                # The 'parts' in session history can be a list of strings,
                # convert each to a dictionary with a 'text' key.
                # Also, ensure no None values are passed to the API.
                formatted_history.append({
                    "role": message['role'],
                    "parts": [{"text": part} for part in message['parts'] if part is not None]
                })
            else:
                # Handle cases where 'parts' might just be a string or unexpected format
                formatted_history.append({
                    "role": message['role'],
                    "parts": [{"text": str(message.get('parts'))}]
                })

        # Start a chat session with the formatted history
        chat = model.start_chat(history=formatted_history)
        
        # Send the new user input to the model
        response = chat.send_message(user_input)
        
        return response.text
    except Exception as e:
        print(f"Error getting Gemini response: {e}")
        return "I'm sorry, I'm having trouble understanding right now. Please try again later."

# --- Creator Mode Chat Response ---
def get_gpt_creator_response(user_input, my_info):
    """
    Generates a response from the Gemini model in creator mode.
    This mode can leverage the 'my_info' (knowledge base) for more specific interactions.
    """
    try:
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        
        # Construct a prompt that includes the creator's request and the bot's knowledge
        # This allows the creator to query or instruct the bot based on its internal info
        prompt = (
            f"You are an AI Ambassador named {my_info.get('Name', 'Shreyash')}, "
            f"created by {my_info.get('Creator', 'Shreyash')}. "
            f"Your date of birth is {my_info.get('DOB', 'N/A')}, "
            f"and your occupation is {my_info.get('Occupation', 'N/A')}. "
            f"Your hobbies include {', '.join(my_info.get('Hobbies', ['N/A']))}. "
            f"Your skills include: Coding Languages - {', '.join(my_info.get('Skills', {}).get('coding language', ['N/A']))}, "
            f"Concepts - {', '.join(my_info.get('Skills', {}).get('Concepts', ['N/A']))}, "
            f"Libraries - {', '.join(my_info.get('Skills', {}).get('Libraries', ['N/A']))}, "
            f"Spoken Languages - {', '.join(my_info.get('Skills', {}).get('languages', ['N/A']))}.\n\n"
            f"The creator has asked: {user_input}\n\n"
            f"Based on your internal knowledge and the creator's query, please respond."
        )
        
        response = model.generate_content(prompt)
        
        return response.text
    except Exception as e:
        print(f"Error getting Gemini creator response: {e}")
        return "I'm sorry, Creator. I encountered an issue while processing your request. Please try again."

