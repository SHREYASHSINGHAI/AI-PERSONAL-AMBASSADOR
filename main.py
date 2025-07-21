import os
import json
import hashlib
import google.generativeai as genai

from textblob import TextBlob  #for sentiment analysis
from collections import defaultdict  #to count the sentiments

from datetime import timedelta, datetime, date  # Added date import
from flask import Flask, request, render_template, session, redirect, url_for
from dotenv import load_dotenv  # For loading environment variables

# Load environment variables from .env file (for local development)
load_dotenv()

app = Flask(__name__)

# --- API Keys & Flask Secret Key Configuration ---

gemini_api_key = os.getenv("GEMINI_API_KEY")
flask_secret_key = os.getenv(
    "FLASK_SECRET_KEY")  # NEW: Separate secret for Flask sessions

if not gemini_api_key:
    print(
        "CRITICAL ERROR: GEMINI_API_KEY environment variable not set. AI functions will fail."
    )
if not flask_secret_key:
    # This is a critical error for session management.
    print(
        "CRITICAL ERROR: FLASK_SECRET_KEY environment variable not set. Flask sessions (login status, chat history) will NOT work correctly. PLEASE SET THIS IN REPLIT SECRETS."
    )
    # For a real application, you might want to raise an exception here or have a default, but for development
    # we'll allow it to run with a warning, knowing sessions won't persist.
    app.config[
        'SECRET_KEY'] = 'a_fallback_dev_secret_key_if_not_set'  # FALLBACK (NOT for production)
else:
    app.config['SECRET_KEY'] = flask_secret_key

# --- Flask Configuration ---
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(
    minutes=30)  # Sessions last 30 minutes


try:
    genai.configure(api_key=gemini_api_key)
except Exception as e:
    print(f"Error configuring Gemini API: {e}")
    print("Ensure GEMINI_API_KEY is correct and has access.")

# Using gemini-2.0-flash as specified in recent attempts.
model = genai.GenerativeModel('gemini-2.0-flash')

BOT_NAME = "Shrey"
CREATOR_NAME = "Shreyash"
PASSWORD_FILE = "creator_password.hash"
INFO_FILE = "myinfo.json"
SENTIMENT_HISTORY_FILE = "user_sentiment_history.json"


# --- Password Setup (Manual for Replit) ---
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
            f"[{BOT_NAME}]    {hashlib.sha256('password123'.encode()).hexdigest()}"
        )
        print(f"---------------------------\n")


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
        "DOB":
        "02/05/2005",  # Added DOB for consistency with previous examples
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
        ["swimming", "play football", "sketching", "painting", "skating"],
    }

def load_sentiment_history():
    #load sentiment history from json file.
    try: 
        with open(SENTIMENT_HISTORY_FILE) as f:
            data = json.load(f)
    #for sentiment count ensure data structure is dictionary
            if not isinstance(data,dict):
                print("f{BOT_NAME} sentiment file is corrupted or in an unexpected format.\n")
                print("resetting")
                return {}
            return data
    except (FileNotFoundError,josn.JSONDecodeError):
        print("{SENTIMENT_HISTORY_FILE} not found or corrupted.Initializing empty sentiment history.")
        return {}

def save_sentiment_history(data):
    #saves sentiment history to json file
    try:
        with open(SENTIMENT_HISTORY_FILE) as f:
            json.dump(data,findent=2)
        return True
    except Exception as e:
        print("f{BOT_NAME} Error in saving sentiments in the sentiment history file.")
        return False
sentiment_history=load_sentiment_history()
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


# --- Helper Functions ---
def calculate_age(dob_str):
    """Calculates age based on a 'MM/DD/YYYY' DOB string."""
    try:
        # Parse the DOB string into a datetime object
        dob = datetime.strptime(dob_str, "%m/%d/%Y").date()
        today = date.today()

        # Calculate age
        age = today.year - dob.year - (
            (today.month, today.day) < (dob.month, dob.day))
        return age
    except ValueError:
        return None  # Return None if DOB string is invalid


# --- AI Interaction Logic ---
def ask_ai(question, current_my_info, is_creator_session,
           session_chat_history):
    """Centralized response generator with context and creator awareness."""

    # Calculate creator's age if DOB is available
    creator_age = None
    current_my_info_for_ai = current_my_info.copy()  # Start with a copy
    if "DOB" in current_my_info:
        calculated_age = calculate_age(current_my_info["DOB"])
        if calculated_age is not None:
            current_my_info_for_ai[
                "Age"] = calculated_age  # Add age to the copy for AI context
        # else: DOB is invalid, so "Age" won't be added to the context

    update_instruction = ""
    if is_creator_session:
        update_instruction = f"""
        IMPORTANT CREATOR MODE INSTRUCTIONS:
        If the user (Creator) expresses a clear intent to MODIFY, ADD, or REMOVE information about {CREATOR_NAME}'s profile, you MUST respond with a JSON object ONLY. This applies to updating simple fields, adding/removing items from lists, or adding/removing items from nested lists (like skills categories), adding/removing lists.

        You MUST use one of the following JSON formats. Do NOT include any additional text or markdown outside the JSON block. The system will handle confirmation messages.

        JSON RESPONSE FORMATS:

        1. To UPDATE a simple field (e.g., Name, Occupation, DOB, etc.):
            {{
              "action": "update",
              "field": "[exact_field_name]",
              "value": "[new_value]"
            }}
            Example user input: "Change my occupation to Software Engineer."
            Example JSON: {{"action": "update", "field": "Occupation", "value": "Software Engineer"}}
            Example user input: "My favorite color is blue." (If 'favorite color' doesn't exist, create it)
            Example JSON: {{"action": "update", "field": "Favorite Color", "value": "blue"}}


        2. To ADD an item to a list (e.g., Hobbies or a sub-list within Skills like 'coding language'):
            {{
              "action": "add_item",
              "field": "[exact_main_field_name]",
              "sub_field": "[exact_sub_field_name_if_nested_list_else_null]",
              "item": "[item_to_add]"
            }}
            Example user input for Hobbies: "Add reading to my hobbies."
            Example JSON: {{"action": "add_item", "field": "Hobbies", "sub_field": null, "item": "reading"}}
            Example user input for Skills->coding language: "Add JavaScript to my coding language skills."
            Example JSON: {{"action": "add_item", "field": "Skills", "sub_field": "coding language", "item": "JavaScript"}}
            Example user input for new top-level list: "Add swimming to my new sport activities."
            Example JSON: {{"action": "add_item", "field": "Sport Activities", "sub_field": null, "item": "swimming"}}
            Note: If the main field is a simple list, 'sub_field' should be 'null'.

        3. To REMOVE an item from a list (e.g., Hobbies or a sub-list within Skills):
            {{
              "action": "remove_item",
              "field": "[exact_main_field_name]",
              "sub_field": "[exact_sub_field_name_if_nested_list_else_null]",
              "item": "[item_to_remove]"
            }}
            Example user input for Hobbies: "Remove swimming from my hobbies."
            Example JSON: {{"action": "remove_item", "field": "Hobbies", "sub_field": null, "item": "swimming"}}
            Example user input for Skills->Libraries: "Remove Numpy from my Libraries."
            Example JSON: {{"action": "remove_item", "field": "Skills", "sub_field": "Libraries", "item": "Numpy"}}

        GENERAL RULES FOR CREATOR MODE:
        * Always try to infer the correct `field`, `sub_field`, and `item`/`value` from the user's natural language request.
        * Be smart about recognizing categories like 'coding language', 'Libraries', 'Concepts', 'languages' under 'Skills'.
        * The field names in your JSON (e.g., "Hobbies", "Skills", "coding language") MUST exactly match the keys in the `CREATOR INFORMATION` JSON provided below, including casing.
        * If the request is ambiguous or cannot be clearly mapped to an update/add/remove action, or is a general question, respond naturally asking for clarification (DO NOT send JSON in this case).
        """
    else:  # Guest user
        update_instruction = "If the user (Guest) asks to 'update', 'add', or 'remove' information, state '⛔ Verification required' and explain that only the Creator can make updates. Do not attempt to modify any information. Respond naturally to all other questions."

    # Use a limited portion of the session chat history for context
    # This helps keep the prompt size manageable.
    recent_history = ""
    if session_chat_history:
        recent_history = "\nLast 3 exchanges (for context only):"
        for entry in session_chat_history[-6:]:  # Last 3 user/model pairs
            role = "USER" if entry["role"] == "user" else "BOT"
            recent_history += f"\n{role}: {entry['parts'][0]}"

    # Provide the current date to the AI for time-sensitive calculations
    current_date_info = f"\nCURRENT DATE: {date.today().strftime('%m/%d/%Y')}"

    prompt = f"""
ROLE:
- You are {BOT_NAME}, a friendly and creator's AI Ambassador.
- Your Creator: {CREATOR_NAME}.
- Current user status: {'Creator' if is_creator_session else 'Guest'}.

RULES FOR ALL INTERACTIONS:
1. For creator info questions: Use the provided `my_info` data to answer questions about {CREATOR_NAME}.
2. Style: Friendly, concise, and informative.
3. Respond to questions as {BOT_NAME}, the ambassador, not as the creator.
4. Absolutely DO NOT start your response with any greeting (e.g., "Hello," "Hi," "Hi guest," "Hi creator," "Hey there"). This includes introductions of yourself or stating your name. The initial greeting is handled separately by the system at the start of the chat. Just directly answer the user's question or respond to their input, starting immediately with relevant information.
5. Absolutely DO NOT directly copy or reprint the 'CREATOR INFORMATION' JSON block or large parts of it in your response. Synthesize the information into natural, concise language.
6. If the user asks about your own abilities or purpose, explain that you are {BOT_NAME}, the AI Ambassador(not personal assistant)) for {CREATOR_NAME}, and that you can answer questions about.

{update_instruction}

{current_date_info}

CREATOR INFORMATION:
{json.dumps(current_my_info_for_ai, indent=2)}
{recent_history}

USER QUESTION: {question}
"""
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        # Log the full exception for debugging
        print(f"DEBUG: Error generating response from AI: {e}")
        return f"⚠️ Error generating response from AI: {str(e)}. Please check GEMINI_API_KEY and review the console for details."


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

    #SENTIMENT ANALYSIS AND LOGGING   
    sentiment_analysis_result = analyze_sentiment(user_input)
    log_sentiment(user_input, sentiment_analysis_result)

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

    # --- AI Interaction and Info Modification ---
    else:
        ai_raw_response = ask_ai(user_input, my_info, is_creator_logged_in,
                                 session_chat_history)

        # Try to parse the AI's response as JSON
        try:
            # Strip any leading/trailing whitespace or markdown code blocks
            ai_raw_response_cleaned = ai_raw_response.strip()
            if ai_raw_response_cleaned.startswith("```json"):
                ai_raw_response_cleaned = ai_raw_response_cleaned[7:]
            if ai_raw_response_cleaned.endswith("```"):
                ai_raw_response_cleaned = ai_raw_response_cleaned[:-3]
            ai_raw_response_cleaned = ai_raw_response_cleaned.strip()

            ai_response_json = json.loads(ai_raw_response_cleaned)

            # If AI returned a valid JSON update instruction AND user is creator
            if is_creator_logged_in and "action" in ai_response_json:
                action = ai_response_json["action"]
                field = ai_response_json.get("field")
                value = ai_response_json.get("value")
                sub_field = ai_response_json.get("sub_field")
                item = ai_response_json.get("item")

                message_prefix = f"{BOT_NAME}: "  # Consistent prefix for bot responses

                # --- Handle 'update' action ---
                if action == "update" and field:
                    actual_field_key = next((k for k in my_info.keys()
                                             if k.lower() == field.lower()),
                                            None)

                    if field.lower() == "creator":
                        bot_response = message_prefix + "Sorry, the 'Creator' field cannot be changed directly for security reasons."
                    elif actual_field_key:  # Update existing field
                        old_value = my_info[actual_field_key]
                        # Type conversion for DOB if needed (example)
                        if actual_field_key.lower(
                        ) == "dob":  # Case-insensitive check for DOB
                            try:
                                # Attempt to parse date to ensure valid format, or keep as string
                                datetime.strptime(
                                    str(value), "%m/%d/%Y"
                                )  # Ensure value is string for strptime
                            except ValueError:
                                bot_response = message_prefix + f"Invalid date format for DOB. Please use MM/DD/YYYY."
                            else:
                                my_info[actual_field_key] = value
                                if save_info(my_info):
                                    bot_response = message_prefix + f"Updated '{actual_field_key}' from '{old_value}' to '{value}' successfully."
                                else:
                                    bot_response = message_prefix + f"Error updating '{actual_field_key}'."
                        elif isinstance(my_info[actual_field_key],
                                        (list, dict)):
                            bot_response = message_prefix + f"'{actual_field_key}' is a list or dictionary. Use 'add_item' or 'remove_item' for lists, or specify the sub-field for dictionaries."
                        else:  # Simple field update
                            my_info[actual_field_key] = value
                            if save_info(my_info):
                                bot_response = message_prefix + f"Updated '{actual_field_key}' from '{old_value}' to '{value}' successfully."
                            else:
                                bot_response = message_prefix + f"Error updating '{actual_field_key}'."
                    else:  # Add new top-level field
                        my_info[field] = value
                        if save_info(my_info):
                            bot_response = message_prefix + f"Added new information: '{field}' as '{value}' successfully."
                        else:
                            bot_response = message_prefix + f"Error adding new information '{field}'."

                # --- Handle 'add_item' action ---
                elif action == "add_item" and field and item is not None:
                    actual_field_key = next((k for k in my_info.keys()
                                             if k.lower() == field.lower()),
                                            None)

                    if actual_field_key is None and sub_field is None:
                        # Case 1: Adding to a brand new top-level list (e.g., "Awards": ["Best Coder"])
                        my_info[field] = [item]
                        if save_info(my_info):
                            bot_response = message_prefix + f"Created new section '{field}' and added '{item}' successfully."
                        else:
                            bot_response = message_prefix + f"Error creating new section or adding item."
                    elif actual_field_key:
                        # Case 2: Adding to an existing field
                        if sub_field:
                            # Case 2a: Nested list (e.g., Skills -> coding language)
                            if isinstance(
                                    my_info[actual_field_key], dict
                            ) and sub_field in my_info[actual_field_key]:
                                if isinstance(
                                        my_info[actual_field_key][sub_field],
                                        list):
                                    if item not in my_info[actual_field_key][
                                            sub_field]:
                                        my_info[actual_field_key][
                                            sub_field].append(item)
                                        if save_info(my_info):
                                            bot_response = message_prefix + f"'{item}' added to '{sub_field}' under '{actual_field_key}' successfully."
                                        else:
                                            bot_response = message_prefix + f"Error adding '{item}' to '{sub_field}'."
                                    else:
                                        bot_response = message_prefix + f"'{item}' is already in '{sub_field}' under '{actual_field_key}'."
                                else:
                                    # Handle scenario where sub_field exists but is not a list
                                    bot_response = message_prefix + f"'{sub_field}' under '{actual_field_key}' is not a list. Cannot add item."
                            else:
                                # Handle scenario where actual_field_key is not a dict or sub_field doesn't exist
                                bot_response = message_prefix + f"'{actual_field_key}' is not a dictionary or '{sub_field}' does not exist under it. Cannot add nested item."
                        else:
                            # Case 2b: Simple list (e.g., Hobbies)
                            if isinstance(my_info[actual_field_key], list):
                                if item not in my_info[actual_field_key]:
                                    my_info[actual_field_key].append(item)
                                    if save_info(my_info):
                                        bot_response = message_prefix + f"'{item}' added to '{actual_field_key}' successfully."
                                    else:
                                        bot_response = message_prefix + f"Error adding '{item}' to '{actual_field_key}'."
                                else:
                                    bot_response = message_prefix + f"'{item}' is already in '{actual_field_key}'."
                            else:
                                # Handle scenario where field exists but is not a list
                                bot_response = message_prefix + f"Cannot add '{item}'. '{actual_field_key}' is not a list. Try 'update my info: {actual_field_key} to [new value]' to change its value or consider removing it first if you want to convert it to a list."
                    else:
                        bot_response = message_prefix + f"Could not find or add to section '{field}'. Please specify correctly."

                # --- Handle 'remove_item' action ---
                elif action == "remove_item" and field and item is not None:
                    actual_field_key = next((k for k in my_info.keys()
                                             if k.lower() == field.lower()),
                                            None)

                    if actual_field_key is None:
                        bot_response = message_prefix + f"Section '{field}' does not exist. Nothing to remove."
                    elif sub_field:  # Nested list
                        if isinstance(
                                my_info[actual_field_key], dict
                        ) and sub_field in my_info[actual_field_key]:
                            if isinstance(my_info[actual_field_key][sub_field],
                                          list):
                                if item in my_info[actual_field_key][
                                        sub_field]:
                                    my_info[actual_field_key][
                                        sub_field].remove(item)
                                    if save_info(my_info):
                                        bot_response = message_prefix + f"Removed '{item}' from '{sub_field}' under '{actual_field_key}' successfully."
                                    else:
                                        bot_response = message_prefix + f"Error removing '{item}' from '{sub_field}'."
                                else:
                                    bot_response = message_prefix + f"'{item}' is not found in '{sub_field}' under '{actual_field_key}'."
                            else:
                                bot_response = message_prefix + f"'{sub_field}' under '{actual_field_key}' is not a list. Cannot remove item."
                        else:
                            bot_response = message_prefix + f"'{actual_field_key}' is not a dictionary or '{sub_field}' does not exist under it. Cannot remove nested item."
                    else:  # Simple list
                        if isinstance(my_info[actual_field_key], list):
                            if item in my_info[actual_field_key]:
                                my_info[actual_field_key].remove(item)
                                if save_info(my_info):
                                    bot_response = message_prefix + f"Removed '{item}' from '{actual_field_key}' successfully."
                                else:
                                    bot_response = message_prefix + f"Error removing '{item}' from '{actual_field_key}'."
                            else:
                                bot_response = message_prefix + f"'{item}' is not found in '{actual_field_key}'."
                        else:
                            bot_response = message_prefix + f"Cannot remove '{item}'. '{actual_field_key}' is not a list."

                # Fallback for unrecognized JSON action (shouldn't happen with good prompt)
                else:
                    bot_response = message_prefix + f"Received an unclear or incomplete update instruction from AI (JSON action not recognized). Raw: {ai_raw_response_cleaned}"
            else:
                # This branch is taken if:
                # 1. AI returned valid JSON but 'action' was missing or invalid.
                # 2. User is NOT logged in as creator, but AI still returned JSON (shouldn't happen with proper prompt).
                # In these cases, we fall back to AI's natural language response.
                bot_response = ai_raw_response
        except json.JSONDecodeError as e:
            # This is where the Internal Server Error might originate if AI doesn't return JSON
            # Log the problematic response for debugging
            print(
                f"DEBUG: JSONDecodeError: AI response was not valid JSON: '{ai_raw_response_cleaned}' Error: {e}"
            )
            bot_response = ai_raw_response  # Fallback to showing AI's raw response
        except Exception as e:
            # Catch any other error during AI response processing
            print(
                f"DEBUG: General Error processing AI response: {e}, Raw response: '{ai_raw_response}'"
            )
            bot_response = f"⚠️ An internal error occurred while processing AI response: {str(e)}. Please try again."

    # Update session chat history for the AI's context in future turns
    # We store a limited number of recent exchanges to keep the prompt size manageable.
    session_chat_history.append({"role": "user", "parts": [user_input]})
    session_chat_history.append({"role": "model", "parts": [bot_response]})
    session['chat_history'] = session_chat_history[-6:]  # Keep last 3 user and 3 model messages

    # Return the bot's response and creator status as JSON to the web page
    return {'response': bot_response, 'is_creator': is_creator_logged_in}

def analyze_sentiment(text):
     """Analyzes the sentiment of the given text using TextBlob."""
    analysis = TextBlob(text)
    polarity = analysis.sentiment.polarity
    
    if polarity > 0.1: # A small threshold to consider as positive
        sentiment_label = "positive"
    elif polarity < -0.1: # A small threshold to consider as negative
        sentiment_label = "negative"
    else:
        sentiment_label = "neutral"
    
    return {
        "text": text,
        "polarity": polarity,
        "subjectivity": analysis.sentiment.subjectivity,
        "sentiment_label": sentiment_label
    }
def log_sentiment(user_input, sentiment_data):
    """Logs the user input and its sentiment data to the history file."""
    global sentiment_history # Access the global sentiment_history dictionary
    
    # Use today's date as a key for daily logging
    today_str = date.today().strftime("%Y-%m-%d")
    
    if today_str not in sentiment_history:
        sentiment_history[today_str] = {
            "total_interactions": 0,
            "sentiment_counts": {"positive": 0, "negative": 0, "neutral": 0},
            "interactions": [] # To store details of each interaction
        }
    
    sentiment_history[today_str]["total_interactions"] += 1
    sentiment_history[today_str]["sentiment_counts"][sentiment_data["sentiment_label"]] += 1
    
    # Store the full interaction for review, including timestamp
    sentiment_history[today_str]["interactions"].append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_input": user_input,
        "sentiment": sentiment_data["sentiment_label"],
        "polarity": sentiment_data["polarity"]
    })
    
    save_sentiment_history(sentiment_history)

# New endpoint to provide initial creator status to the frontend
@app.route('/chat_status', methods=['GET'])
def chat_status():
    is_creator_logged_in = session.get('is_creator_logged_in', False)
    return {'is_creator': is_creator_logged_in}
    
@app.route('/review_sentiment')
def review_sentiment():
    if not session.get('is_creator_logged_in'):
        return redirect(url_for('index')) # Redirect if not logged in
    current_sentiment_history = load_sentiment_history()
    sentiment_display_data = []
    for day, data in current_sentiment_history.items():
        sentiment_display_data.append({
            "date": day,
            "total_interactions": data["total_interactions"],
            "positive": data["sentiment_counts"].get("positive", 0),
            "negative": data["sentiment_counts"].get("negative", 0),
            "neutral": data["sentiment_counts"].get("neutral", 0),
            "interactions_detail": data["interactions"]
        })
    # Sort by date, newest first
    sentiment_display_data.sort(key=lambda x: x['date'], reverse=True)
    return render_template('review_sentiment.html', sentiment_data=sentiment_display_data)



# --- This part ensures the Flask app runs when Replit starts it ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
