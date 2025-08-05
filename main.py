import os
import json
import smtplib
import ssl
import random
import string
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
from werkzeug.exceptions import BadRequest
from dotenv import load_dotenv
from sentiment_analysis import perform_sentiment_analysis_lazy_load # Ensure this function is updated
from gpt_model import get_gpt_response, get_gpt_creator_response # Ensure this file exists and is correct
from transformers import pipeline # Needed for lazy loading the sentiment pipeline
import hashlib # Import hashlib for password hashing

# Load environment variables
load_dotenv()

# Set up Flask
app = Flask(__name__)
# Flask Secret Key: Essential for session security. Uses a default if not set in .env.
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'a_very_secret_default_key_for_flask_sessions')
app.permanent_session_lifetime = datetime.timedelta(days=7)

# Load creator and bot info - now with defaults directly in code
BOT_NAME = os.environ.get('BOT_NAME', 'Shreyash') # Default Bot Name
CREATOR_NAME = os.environ.get('CREATOR_NAME', 'Shreyash') # Default Creator Name
CREATOR_EMAIL = os.environ.get('CREATOR_EMAIL', 'creator@aiambassador.com') # Default Creator Email
# CREATOR_PASSWORD is no longer directly used for verification, but kept for reference if needed
CREATOR_PASSWORD = os.environ.get('CREATOR_PASSWORD', 'password') 

# Email configuration (These are no longer used for login, and are now optional)
# They are kept here in case you re-introduce email functionality later.
EMAIL_HOST = os.environ.get('EMAIL_HOST')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 't')


# File paths
MY_INFO_FILE = os.path.join(os.path.dirname(__file__), 'myinfo.json')
CONVERSATION_SENTIMENT_LOG = os.path.join(os.path.dirname(__file__), 'conversation_sentiment.log')
# Define the path for the creator password hash file
PASSWORD_FILE = os.path.join(os.path.dirname(__file__), 'creator_password.hash')


# Global variable for lazy-loading the sentiment analysis model
sentiment_analysis_pipeline = None

def get_sentiment_pipeline():
    """
    Lazily loads the sentiment analysis pipeline.
    """
    global sentiment_analysis_pipeline
    if sentiment_analysis_pipeline is None:
        print("Loading sentiment analysis model...")
        # You might want to specify a smaller model here for better memory usage
        # e.g., pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")
        sentiment_analysis_pipeline = pipeline("sentiment-analysis")
        print("Model loaded successfully.")
    return sentiment_analysis_pipeline

# Translation dictionary for UI elements
TRANSLATIONS = {
    'en': {
        'menu': 'Menu',
        'logout': 'Logout',
        'creator_logout': 'Creator Logout',
        'enable_creator_mode': 'Enable Creator Mode',
        'disable_creator_mode': 'Disable Creator Mode',
        'sentiment_review': 'Sentiment Review',
        'export_sentiment_data': 'Export Sentiment Data',
        'manage_knowledge': 'Manage Knowledge',
        'type_message': 'Type your message...',
        'voice_output_on': 'Voice Output: On',
        'voice_output_off': 'Voice Output: Off',
        'dark_mode': 'Dark Mode',
        'light_mode': 'Light Mode',
        'select_language': 'Select Language'
    },
    'es': {
        'menu': 'Menú',
        'logout': 'Cerrar sesión',
        'creator_logout': 'Cerrar sesión del Creador',
        'enable_creator_mode': 'Habilitar modo creador',
        'disable_creator_mode': 'Deshabilitar modo creador',
        'sentiment_review': 'Revisión de Sentimientos',
        'export_sentiment_data': 'Exportar Datos de Sentimientos',
        'manage_knowledge': 'Gestionar Conocimiento',
        'type_message': 'Escribe tu mensaje...',
        'voice_output_on': 'Salida de voz: Activada',
        'voice_output_off': 'Salida de voz: Desactivada',
        'dark_mode': 'Modo Oscuro',
        'light_mode': 'Modo Claro',
        'select_language': 'Seleccionar Idioma'
    }
}

# Helper Functions
def load_info():
    if not os.path.exists(MY_INFO_FILE):
        return {}
    try:
        with open(MY_INFO_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_info(info_data):
    with open(MY_INFO_FILE, 'w') as f:
        json.dump(info_data, f, indent=2)

def verify_creator(password_attempt):
    """
    Verifies the creator's password against a stored hash in 'creator_password.hash'.
    If the file doesn't exist, it prints a message and returns False.
    """
    try:
        with open(PASSWORD_FILE, 'r') as f:
            stored_hash = f.read().strip()
        
        # Hash the provided password attempt and compare
        if hashlib.sha256(password_attempt.encode()).hexdigest() == stored_hash:
            return True
        else:
            print("Creator password verification failed: Incorrect password.")
            return False
    except FileNotFoundError:
        print(f"Creator password file '{PASSWORD_FILE}' not found.")
        print("Please create it manually. For example, to hash 'your_password':")
        print("  echo -n 'your_password' | sha256sum > creator_password.hash")
        return False
    except Exception as e:
        print(f"An error occurred during password verification: {e}")
        return False

def is_creator_logged_in():
    return session.get('is_creator_logged_in') and session.get('logged_in_user') == CREATOR_EMAIL

def log_conversation_sentiment(chat_history, user_email):
    """
    Calculates the overall sentiment of a conversation and logs it to a file.
    The overall sentiment is determined by the most frequent sentiment label.
    """
    if not chat_history:
        return

    sentiment_counts = {'positive': 0, 'negative': 0, 'neutral': 0}
    sentiment_pipeline = get_sentiment_pipeline()
    
    # Process each user message in the chat history
    for message in chat_history:
        if message['role'] == 'user':
            user_input = message['parts'][0]
            # Use the lazy-loaded pipeline
            sentiment_result = perform_sentiment_analysis_lazy_load(user_input, sentiment_pipeline)
            sentiment_label = sentiment_result.get('label', 'neutral').lower()
            sentiment_counts[sentiment_label] += 1
            
    # Determine the overall sentiment
    overall_sentiment = max(sentiment_counts, key=sentiment_counts.get)
    if sentiment_counts[overall_sentiment] == 0:
        overall_sentiment = 'neutral'

    timestamp = datetime.datetime.now().isoformat()
    log_line = f"Timestamp: {timestamp} | User: {user_email} | Overall Conversation Sentiment: {overall_sentiment}\n"

    with open(CONVERSATION_SENTIMENT_LOG, 'a') as f:
        f.write(log_line)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in_user' not in session:
            # Redirect to the single login page
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Combined Login Route ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    error_message = None
    if request.method == 'POST':
        user_email = request.form.get('email')
        password_attempt = request.form.get('password') 

        if not user_email:
            error_message = "Email is required."
        elif user_email == CREATOR_EMAIL:
            # For creator, verify password from file
            if verify_creator(password_attempt):
                session['logged_in_user'] = user_email
                session['is_creator_logged_in'] = True
                session['is_creator_mode_active'] = True
                session.permanent = True
                session.pop('chat_history', None)
                return redirect(url_for('index'))
            else:
                error_message = "Invalid password for creator."
        else:
            # For non-creator users, just log them in with their email (password is ignored)
            session['logged_in_user'] = user_email
            session['is_creator_logged_in'] = False # Ensure non-creators are not marked as creator
            session['is_creator_mode_active'] = False
            session.permanent = True
            session.pop('chat_history', None)
            return redirect(url_for('index'))
            
    return render_template('login.html', bot_name=BOT_NAME, creator_name=CREATOR_NAME, error=error_message)

@app.route('/logout_user')
def logout_user():
    # Log the conversation sentiment before logging out
    log_conversation_sentiment(session.get('chat_history', []), session.get('logged_in_user'))
    session.pop('logged_in_user', None)
    session.pop('chat_history', None)
    session.pop('is_creator_logged_in', None)
    session.pop('is_creator_mode_active', None)
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    # Log the conversation sentiment before logging out
    log_conversation_sentiment(session.get('chat_history', []), session.get('logged_in_user'))
    session.pop('logged_in_user', None)
    session.pop('is_creator_logged_in', None)
    session.pop('is_creator_mode_active', None)
    session.pop('chat_history', None)
    return redirect(url_for('login'))

# --- Main Chat Routes ---
@app.route('/')
@login_required
def index():
    my_info = load_info()
    is_creator = session.get('logged_in_user') == CREATOR_EMAIL
    lang = session.get('language', 'en')
    return render_template(
        'index.html',
        bot_name=BOT_NAME,
        user_email=session.get('logged_in_user'),
        is_creator=is_creator,
        is_creator_mode_active=session.get('is_creator_mode_active', False),
        translations=TRANSLATIONS.get(lang, TRANSLATIONS['en']),
        current_language=lang
    )

@app.route('/chat', methods=['POST'])
@login_required
def chat():
    user_input = request.form.get('user_input')
    if not user_input:
        raise BadRequest('User input is required.')

    my_info = load_info()
    session_chat_history = session.get('chat_history', [])
    lang = session.get('language', 'en')
    user_email = session.get('logged_in_user') # Get the current logged-in user's email
    
    if is_creator_logged_in() and session.get('is_creator_mode_active', False):
        bot_response = get_gpt_creator_response(user_input, my_info)
    else:
        bot_response = get_gpt_response(user_input, my_info, session_chat_history, lang)
    
    # Store user's email along with their message in the session chat history
    session_chat_history.append({"role": "user", "parts": [user_input], "email": user_email})
    session_chat_history.append({"role": "model", "parts": [bot_response]})
    
    session['chat_history'] = session_chat_history[-6:]
    
    return jsonify({'response': bot_response, 'timestamp': datetime.datetime.now().isoformat()})

@app.route('/get_chat_history')
@login_required
def get_chat_history():
    return jsonify({'history': session.get('chat_history', [])})

@app.route('/toggle_mode')
@login_required
def toggle_mode():
    if is_creator_logged_in():
        session['is_creator_mode_active'] = not session.get('is_creator_mode_active', False)
    # Log the conversation sentiment before toggling mode, as this effectively ends a "conversation"
    log_conversation_sentiment(session.get('chat_history', []), session.get('logged_in_user'))
    session.pop('chat_history', None)
    return redirect(url_for('index'))

@app.route('/set_language', methods=['POST'])
@login_required
def set_language():
    language = request.form.get('language')
    if language in TRANSLATIONS:
        session['language'] = language
    return jsonify({'status': 'success'})

# --- CREATOR TOOLS ROUTES ---
# The following routes for sentiment review and export have been disabled
# to align with the new logging requirement of logging a single overall
# sentiment per conversation.

@app.route('/review_sentiment')
@login_required
def review_sentiment():
    # This feature is no longer supported with the new sentiment logging method.
    return "This feature is no longer available."

@app.route('/export_sentiment')
@login_required
def export_sentiment():
    # This feature is no longer supported with the new sentiment logging method.
    return "This feature is no longer available."

@app.route('/manage_knowledge', methods=['GET', 'POST'])
@login_required
def manage_knowledge():
    if not is_creator_logged_in():
        return redirect(url_for('login')) # Redirect to the single login page

    my_info = load_info()
    message = None
    
    if request.method == 'POST':
        try:
            new_info = {
                "Creator": request.form.get("Creator", ""),
                "Name": request.form.get("Name", ""),
                "DOB": request.form.get("DOB", ""),
                "Occupation": request.form.get("Occupation", ""),
                "Skills": {
                    "coding language": request.form.get("skills_coding_language", "").split(','),
                    "Concepts": request.form.get("skills_concepts", "").split(','),
                    "Libraries": request.form.get("skills_libraries", "").split(','),
                    "languages": request.form.get("languages", "").split(',') # Corrected from skills_languages to languages
                },
                "Hobbies": request.form.get("Hobbies", "").split(','),
                "Projects": []
            }
            for key in new_info["Skills"]:
                new_info["Skills"][key] = [item.strip() for item in new_info["Skills"][key]]
            new_info["Hobbies"] = [item.strip() for item in new_info["Hobbies"]]

            save_info(new_info)
            message = "Knowledge base updated successfully!"
            my_info = new_info
        except Exception as e:
            message = f"Error saving knowledge base: {e}"

    skills_data = {
        "coding_language": ", ".join(my_info.get("Skills", {}).get("coding language", [])),
        "Concepts": ", ".join(my_info.get("Skills", {}).get("Concepts", [])),
        "Libraries": ", ".join(my_info.get("Skills", {}).get("Libraries", [])),
        "languages": ", ".join(my_info.get("Skills", {}).get("languages", []))
    }
    hobbies_data = ", ".join(my_info.get("Hobbies", []))

    return render_template(
        'manage_knowledge.html',
        my_info=my_info,
        skills=skills_data,
        hobbies=hobbies_data,
        message=message
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
