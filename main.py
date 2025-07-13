import os
import json
import hashlib
from datetime import timedelta, datetime
from flask import Flask, request, render_template, session, redirect, url_for
from dotenv import load_dotenv  # For loading environment variables

# Load environment variables from .env file (for local development)
# In Replit, secrets are directly accessible via os.getenv.
load_dotenv()

app = Flask(__name__)

# --- GEMINI API Key Configuration & Flask Secret Key ---
# IMPORTANT: You MUST set your GEMINI_API_KEY in Replit Secrets.
# This single key will now be used for both Gemini API and Flask session security.
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    # In a production web app, you would log this error and maybe show a maintenance page.
    print(
        "CRITICAL ERROR: GEMINI_API_KEY environment variable not set. AI functions and session security will fail."
    )
    # Exit is not used in a web server context as it would crash the server.
    # The application will continue to run, but AI responses and sessions will error.

# --- Flask Configuration ---
# WARNING: Using GEMINI_API_KEY as SECRET_KEY is NOT recommended for production.
# It significantly reduces the security of your Flask sessions if the API key is compromised.
app.config[
    'SECRET_KEY'] = api_key  # Using the single API key as the Flask Secret Key
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(
    minutes=30)  # Sessions last 30 minutes

import google.generativeai as genai
try:
    genai.configure(api_key=api_key)
    # Test a simple model call to ensure API key works.
    # model_test = genai.GenerativeModel('gemini-pro')
    # model_test.generate_content("hello", safety_settings=[{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}])
except Exception as e:
    print(f"Error configuring Gemini API: {e}")
    print("Ensure GEMINI_API_KEY is correct and has access.")

# Using gemini-pro for wider compatibility and speed.
# You can change to 'gemini-2.0-flash' if you have access and prefer it.
model = genai.GenerativeModel('gemini-2.0-flash')

BOT_NAME = "Shrey"
CREATOR_NAME = "Shreyash"
PASSWORD_FILE = "creator_password.hash"
INFO_FILE = "my_info.json"


# --- Password Setup (Manual for Replit) ---
# This function is just for guidance. You need to manually create
# 'creator_password.hash' in Replit's file explorer and put the SHA256 hash inside it.
def setup_password_guidance():
    if not os.path.exists(PASSWORD_FILE):
        print(f"\n--- IMPORTANT SETUP STEP ---")
        print(
            f"[{BOT_NAME}] The password file '{PASSWORD_FILE}' was not found.")
        print(
            f"[{BOT_NAME}] To enable Creator login, you must manually create this file in Replit's file explorer."
        )
        print(
            f"[{BOT_NAME}] Then, put the SHA256 hash of your desired password inside it."
        )
        print(
            f"[{BOT_NAME}] Example: For password 'password123', the hash is: ")
        print(
            f"[{BOT_NAME}]   {hashlib.sha256('password123'.encode()).hexdigest()}"
        )
        print(f"---------------------------\n")


# Call this once at startup to guide the user if the file is missing
setup_password_guidance()


# --- SECURITY VERIFICATION ---
def verify_creator(password_attempt):
    try:
        with open(PASSWORD_FILE, 'r') as f:
            stored_hash = f.read().strip()
    except FileNotFoundError:
        print(
            f"[{BOT_NAME}] Warning: '{PASSWORD_FILE}' not found during verification. Creator login will not work."
        )
        return False
    except Exception as e:
        print(
            f"[{BOT_NAME}] Error reading password file for verification: {e}")
        return False

    attempt_hash = hashlib.sha256(password_attempt.encode()).hexdigest()
    return attempt_hash == stored_hash


# --- DATA MANAGEMENT ---
def get_default_info():
    return {
        "Creator":
        CREATOR_NAME,
        "Name":
        CREATOR_NAME,
        "Occupation":
        "student pursuing bachelor of technology in the field of artificial intelligence and machine learning",
        "Skills": {
            "coding language": ["python", "C++"],
            "Concepts": [
                "Data Structures", "data preprocessing", "data visualization",
                "machine learning", "deep learning", "model building"
            ],
            "Libraries": [
                "Numpy", "Pandas", "Matplotlib", "Seaborn", "SciKitLearn",
                "Tensorflow", "Keras"
            ],
            "languages": ["Hindi", "English", "little bit German"]
        },
        "Hobbies":
        ["swimming", "play football", "sketching", "painting", "skating"]
    }


def load_info():
    """Loads information from the JSON file or returns default."""
    try:
        with open(INFO_FILE, 'r') as f:
            data = json.load(f)
            # Basic integrity check: ensure the Creator field matches
            if data.get("Creator") != CREATOR_NAME:
                print(
                    f"[{BOT_NAME}] Unauthorized changes detected or creator name mismatch in {INFO_FILE}. Resetting to default."
                )
                return get_default_info()
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        print(
            f"[{BOT_NAME}] {INFO_FILE} not found or corrupted. Creating default info."
        )
        return get_default_info()


def save_info(data):
    """Saves information to the JSON file."""
    data["Creator"] = CREATOR_NAME  # Always enforce Creator tag on save
    try:
        with open(INFO_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        print(
            f"[{BOT_NAME}] Info updated successfully and saved to {INFO_FILE}!"
        )
        return True  # Indicate success
    except Exception as e:
        print(f"[{BOT_NAME}] Error saving information to {INFO_FILE}: {e}")
        return False  # Indicate failure


# Initialize my_info globally when the app starts
my_info = load_info()


# --- AI Interaction Logic ---
def ask_ai(question, current_my_info, is_creator_session,
           session_chat_history):
    """Centralized response generator with context and creator awareness."""

    update_instruction = ""
    if is_creator_session:
        update_instruction = "If the user (Creator) explicitly asks to 'update' specific information, acknowledge and ask for details on what to change. Do NOT directly modify my_info yourself as that's handled by specific commands."
    else:
        update_instruction = "If the user (Guest) asks to 'update' information, state '⛔ Verification required' and explain that only the Creator can make updates. Do not attempt to update any information."

    # Use a limited portion of the session chat history for context
    # This helps keep the prompt size manageable.
    recent_history = ""
    if session_chat_history:
        recent_history = "\nLast 3 exchanges (for context only):"
        for entry in session_chat_history[-6:]:  # Last 3 user/model pairs
            role = "USER" if entry["role"] == "user" else "BOT"
            recent_history += f"\n{role}: {entry['parts'][0]}"

    prompt = f"""
ROLE:
- You are {BOT_NAME}, a friendly and personal assistant
- Your Creator: {CREATOR_NAME}
- Current user status: {'Creator' if is_creator_session else 'Guest'}

RULES:
1. For creator info: Use the provided `my_info` data to answer questions about {CREATOR_NAME}.
2. {update_instruction}
3. Style: Friendly, concise, and informative.
4. Respond to questions as {BOT_NAME}, the assistant, not as the creator.
5. Absolutely DO NOT start your response with any greeting (e.g., "Hello," "Hi," "Hi guest," "Hi creator," "Hey there"). This includes introductions of yourself or stating your name. The initial greeting is handled separately by the system at the start of the chat. Just directly answer the user's question or respond to their input, starting immediately with relevant information.
6. Absolutely DO NOT directly copy or reprint the 'CREATOR INFORMATION' JSON block or large parts of it in your response. Synthesize the information into natural, concise language.

CREATOR INFORMATION:
{json.dumps(current_my_info, indent=2)}
{recent_history}

USER QUESTION: {question}
"""
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"⚠️ Error generating response from AI: {str(e)}. Please check GEMINI_API_KEY."


# *****************************************************************************************************************************

# --- WEB APPLICATION ROUTES ---


@app.route('/')
def index():
    # Make session permanent (controls session cookie expiration)
    session.permanent = True
    # Get creator login status from the session (default to False if not set)
    is_creator_status = session.get('is_creator_logged_in', False)
    return render_template('index.html',
                           bot_name=BOT_NAME,
                           creator_name=CREATOR_NAME,
                           is_creator=is_creator_status)


@app.route('/chat', methods=['POST'])
def chat():
    # Retrieve user-specific chat history and creator status from session
    is_creator_logged_in = session.get('is_creator_logged_in', False)
    # Ensure chat_history is a list, initialize if not present
    session_chat_history = session.get('chat_history', [])

    user_input = request.form['user_input'].strip()
    bot_response = ""

    # Handle creator login command
    if user_input.lower().startswith(
            "i am ") and CREATOR_NAME.lower() in user_input.lower():
        parts = user_input.lower().split(" ", 3)
        if len(parts) >= 4 and parts[0] == 'i' and parts[1] == 'am' and parts[
                2] == CREATOR_NAME.lower():
            password_attempt = parts[3]
            if verify_creator(password_attempt):
                session[
                    'is_creator_logged_in'] = True  # Store status in session
                session.permanent = True  # Make this session permanent for the creator
                bot_response = f"🔓 Verified! Creator privileges activated. Welcome, {CREATOR_NAME}."
            else:
                session['is_creator_logged_in'] = False
                bot_response = "⚠️ Authentication failed. Incorrect password."
        else:
            bot_response = "To log in as Creator, please type 'I am Shreyash [your_password]'."
    # Handle creator logout command
    elif user_input.lower() == "logout":
        session.pop('is_creator_logged_in',
                    None)  # Remove creator status from session
        session.pop('chat_history',
                    None)  # Clear chat history for this user on logout
        bot_response = "👋 You have been logged out. Chat history cleared."
        is_creator_logged_in = False  # Update for current response

    # Handle explicit Update commands for the Creator (update my info:)
    elif user_input.lower().startswith("update my info:"):
        if is_creator_logged_in:
            update_command = user_input[len("update my info:"):].strip()
            if " to " in update_command:
                parts = update_command.split(" to ", 1)
                key_to_update_raw = parts[0].strip()
                new_value = parts[1].strip()
                key_to_update_lower = key_to_update_raw.lower()

                # Special handling for 'Creator' field
                if key_to_update_lower == "creator":
                    bot_response = f"{BOT_NAME}: Sorry, the 'Creator' field cannot be changed directly for security reasons."
                # Direct update for simple fields like 'Name', 'Occupation' etc.
                elif key_to_update_lower == "name":
                    my_info["Name"] = new_value
                    if save_info(my_info):
                        bot_response = f"{BOT_NAME}: Your 'Name' has been updated to '{new_value}'."
                    else:
                        bot_response = f"{BOT_NAME}: Error updating 'Name'."
                elif key_to_update_lower in ["skills", "hobbies"]:
                    bot_response = f"{BOT_NAME}: To update '{key_to_update_raw}', please use more specific commands like 'add skill: [skill]' or 'remove hobby: [hobby]'. Simple 'to' updates are not supported for complex sections."
                else:
                    found_existing_key = None
                    for existing_key in my_info.keys():
                        if existing_key.lower() == key_to_update_lower:
                            found_existing_key = existing_key
                            break

                    if found_existing_key:
                        old_value = my_info[found_existing_key]
                        my_info[found_existing_key] = new_value
                        if save_info(my_info):
                            bot_response = f"{BOT_NAME}: Changed '{found_existing_key}' from '{old_value}' to '{new_value}'."
                        else:
                            bot_response = f"{BOT_NAME}: Error updating '{found_existing_key}'."
                    else:  # If key doesn't exist, add it
                        my_info[key_to_update_raw] = new_value
                        if save_info(my_info):
                            bot_response = f"{BOT_NAME}: Added new information: '{key_to_update_raw}' as '{new_value}'."
                        else:
                            bot_response = f"{BOT_NAME}: Error adding new information."
            else:
                bot_response = f"{BOT_NAME}: Please specify what you'd like to update using 'update my info: [field] to [new value]'. For example: 'update my info: Occupation to Software Engineer'."
        else:
            bot_response = f"{BOT_NAME}: ⛔ Creator verification required to update information."
    # New: Add item to a list-like section (e.g., Hobbies, or a new 'Interests' section)
    elif user_input.lower().startswith(
            "add ") and " to " in user_input.lower():
        if is_creator_logged_in:
            parts = user_input.lower().split(" to ", 1)
            item_part = parts[0].strip()[4:].strip()  # Get item after "add "
            category_key_lower = parts[1].strip()

            if not item_part:
                bot_response = f"{BOT_NAME}: Please specify what you want to add. Example: 'add cycling to hobbies'."
            elif not category_key_lower:
                bot_response = f"{BOT_NAME}: Please specify which section you want to add to. Example: 'add cycling to hobbies'."
            else:
                actual_category_key = next(
                    (k for k in my_info.keys()
                     if k.lower() == category_key_lower), None)

                if actual_category_key is None:  # Category doesn't exist, create it as a list
                    my_info[category_key_lower.title()] = [item_part]
                    if save_info(my_info):
                        bot_response = f"{BOT_NAME}: Created new section '{category_key_lower.title()}' and added '{item_part}'."
                    else:
                        bot_response = f"{BOT_NAME}: Error creating new section or adding item."
                elif isinstance(my_info[actual_category_key],
                                list):  # Category exists and is a list
                    if item_part not in my_info[actual_category_key]:
                        my_info[actual_category_key].append(item_part)
                        if save_info(my_info):
                            bot_response = f"{BOT_NAME}: Added '{item_part}' to '{actual_category_key}'."
                        else:
                            bot_response = f"{BOT_NAME}: Error adding '{item_part}' to '{actual_category_key}'."
                    else:
                        bot_response = f"{BOT_NAME}: '{item_part}' is already in '{actual_category_key}'."
                elif isinstance(
                        my_info[actual_category_key], dict
                ):  # Category exists and is a dictionary (like 'Skills')
                    # This requires further parsing, for simplicity we'll keep it as "cannot add directly"
                    bot_response = f"{BOT_NAME}: Cannot directly add to '{actual_category_key}' as it's a complex section. Please use the 'update my info' command for specific key-value pairs within it, or ask me for details."
                else:  # Category exists but is not a list or dictionary
                    bot_response = f"{BOT_NAME}: Cannot add to '{actual_category_key}' directly. It's not a list. Try 'update my info: {actual_category_key} to [new value]' to change its value."
        else:
            bot_response = f"{BOT_NAME}: ⛔ Creator verification required to add information."
    # New: Remove item from a list-like section
    elif user_input.lower().startswith(
            "remove ") and " from " in user_input.lower():
        if is_creator_logged_in:
            parts = user_input.lower().split(" from ", 1)
            item_part = parts[0].strip()[7:].strip(
            )  # Get item after "remove "
            category_key_lower = parts[1].strip()

            if not item_part:
                bot_response = f"{BOT_NAME}: Please specify what you want to remove. Example: 'remove cycling from hobbies'."
            elif not category_key_lower:
                bot_response = f"{BOT_NAME}: Please specify which section you want to remove from. Example: 'remove cycling from hobbies'."
            else:
                actual_category_key = next(
                    (k for k in my_info.keys()
                     if k.lower() == category_key_lower), None)

                if actual_category_key is None or not isinstance(
                        my_info.get(actual_category_key), list):
                    bot_response = f"{BOT_NAME}: '{category_key_lower}' is not a list or does not exist."
                elif item_part in my_info[actual_category_key]:
                    my_info[actual_category_key].remove(item_part)
                    if save_info(my_info):
                        bot_response = f"{BOT_NAME}: Removed '{item_part}' from '{actual_category_key}'."
                    else:
                        bot_response = f"{BOT_NAME}: Error removing '{item_part}' from '{actual_category_key}'."
                else:
                    bot_response = f"{BOT_NAME}: '{item_part}' is not found in '{actual_category_key}'."
        else:
            bot_response = f"{BOT_NAME}: ⛔ Creator verification required to remove information."
    # All other conversation (defer to AI)
    else:
        bot_response = ask_ai(user_input, my_info, is_creator_logged_in,
                              session_chat_history)

    # Update session chat history for the AI's context in future turns
    # We store a limited number of recent exchanges to keep the prompt size manageable.
    session_chat_history.append({"role": "user", "parts": [user_input]})
    session_chat_history.append({"role": "model", "parts": [bot_response]})
    session['chat_history'] = session_chat_history[
        -6:]  # Keep last 3 user and 3 model messages

    # Return the bot's response and creator status as JSON to the web page
    return {'response': bot_response, 'is_creator': is_creator_logged_in}


# New endpoint to provide initial creator status to the frontend
@app.route('/chat_status', methods=['GET'])
def chat_status():
    is_creator_logged_in = session.get('is_creator_logged_in', False)
    return {'is_creator': is_creator_logged_in}


# --- This part ensures the Flask app runs when Replit starts it ---
if __name__ == '__main__':
    app.run(host='0.0.0.0',
            port=5000)  # Replit automatically exposes this port
