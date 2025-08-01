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
from sentiment_analysis import perform_sentiment_analysis
from gpt_model import get_gpt_response, get_gpt_creator_response

# Load environment variables
load_dotenv()

# Set up Flask
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default-secret-key')
app.permanent_session_lifetime = datetime.timedelta(days=7)

# Load creator and bot info
BOT_NAME = os.environ.get('BOT_NAME', 'Shreyash')
CREATOR_NAME = os.environ.get('CREATOR_NAME', 'Shreyash')
CREATOR_EMAIL = os.environ.get('CREATOR_EMAIL', 'creator@aiambassador.com')
CREATOR_PASSWORD = os.environ.get('CREATOR_PASSWORD', 'password')

# Email configuration for OTP
EMAIL_HOST = os.environ.get('EMAIL_HOST')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 't')

# File paths
MY_INFO_FILE = os.path.join(os.path.dirname(__file__), 'myinfo.json')
SENTIMENT_HISTORY_FILE = os.path.join(os.path.dirname(__file__), 'user_sentiment_history.json')

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

def load_sentiment_history():
    if not os.path.exists(SENTIMENT_HISTORY_FILE):
        return {}
    try:
        with open(SENTIMENT_HISTORY_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_sentiment_history(history_data):
    with open(SENTIMENT_HISTORY_FILE, 'w') as f:
        json.dump(history_data, f, indent=2)

def verify_creator(password):
    return password == CREATOR_PASSWORD

def is_creator_logged_in():
    return session.get('is_creator_logged_in') and session.get('logged_in_user') == CREATOR_EMAIL

def log_sentiment(user_input, sentiment_result, user_email):
    sentiment_history = load_sentiment_history()
    today_str = datetime.date.today().isoformat()

    if today_str not in sentiment_history:
        sentiment_history[today_str] = {
            'total_interactions': 0,
            'sentiment_counts': {'positive': 0, 'negative': 0, 'neutral': 0},
            'interactions': []
        }
    
    sentiment_history[today_str]['total_interactions'] += 1
    sentiment_history[today_str]['sentiment_counts'][sentiment_result.get('label', 'neutral').lower()] += 1
    
    interaction = {
        'timestamp': datetime.datetime.now().isoformat(),
        'user_email': user_email,
        'user_input': user_input,
        'sentiment': sentiment_result
    }
    
    sentiment_history[today_str]['interactions'].append(interaction)
    save_sentiment_history(sentiment_history)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in_user' not in session:
            return redirect(url_for('email_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- OTP and Login Routes ---
def send_otp_email(to_email, otp_code):
    try:
        msg = MIMEMultipart("alternative")
        msg['Subject'] = "Your AI Ambassador Login Code"
        msg['From'] = EMAIL_HOST_USER
        msg['To'] = to_email

        html = f"""
        <html>
          <body>
            <p>Hello,</p>
            <p>Your one-time login code is: <strong>{otp_code}</strong></p>
            <p>This code will expire in 10 minutes.</p>
            <p>Thank you!</p>
          </body>
        </html>
        """
        msg.attach(MIMEText(html, 'html'))
        
        context = ssl.create_default_context()
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            if EMAIL_USE_TLS:
                server.starttls(context=context)
            server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
            server.sendmail(EMAIL_HOST_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

@app.route('/email_login', methods=['GET', 'POST'])
def email_login():
    error_message = None
    if request.method == 'POST':
        user_email = request.form.get('email')
        if not user_email:
            error_message = "Email is required."
        else:
            otp_code = ''.join(random.choices(string.digits, k=6))
            session['otp'] = otp_code
            session['otp_email'] = user_email
            session['otp_time'] = datetime.datetime.now().isoformat()
            
            if send_otp_email(user_email, otp_code):
                session.permanent = True
                return redirect(url_for('verify_otp'))
            else:
                error_message = "Failed to send OTP. Please check your email configuration or try again."
    return render_template('email_login.html', bot_name=BOT_NAME, creator_name=CREATOR_NAME, error=error_message)

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if 'otp' not in session:
        return redirect(url_for('email_login'))

    error_message = None
    if request.method == 'POST':
        user_otp = request.form.get('otp')
        if user_otp == session.get('otp'):
            otp_time = datetime.datetime.fromisoformat(session.get('otp_time'))
            if datetime.datetime.now() - otp_time < datetime.timedelta(minutes=10):
                session.pop('otp')
                session.pop('otp_time')
                session['logged_in_user'] = session.pop('otp_email')
                session.permanent = True
                session.pop('chat_history', None)
                return redirect(url_for('index'))
            else:
                error_message = "OTP has expired. Please request a new one."
        else:
            error_message = "Invalid OTP. Please try again."
    return render_template('verify_otp.html', bot_name=BOT_NAME, creator_name=CREATOR_NAME, error=error_message)

@app.route('/logout_user')
def logout_user():
    session.pop('logged_in_user', None)
    session.pop('chat_history', None)
    return redirect(url_for('email_login'))

# --- CREATOR LOGIN ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    error_message = None
    # Ensure the user logged in with the creator email before showing the password form
    if session.get('logged_in_user') != CREATOR_EMAIL:
        return redirect(url_for('email_login'))

    if request.method == 'POST':
        password_attempt = request.form.get('password')
        if verify_creator(password_attempt):
            session['is_creator_logged_in'] = True
            session['is_creator_mode_active'] = True
            session.permanent = True
            session.pop('chat_history', None)
            return redirect(url_for('index'))
        else:
            error_message = "Invalid password. Please try again."
    return render_template('login.html', creator_name=CREATOR_NAME, error=error_message)

@app.route('/logout')
def logout():
    session.pop('logged_in_user', None)
    session.pop('is_creator_logged_in', None)
    session.pop('is_creator_mode_active', None)
    session.pop('chat_history', None)
    return redirect(url_for('email_login'))

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
    
    if is_creator_logged_in() and session.get('is_creator_mode_active', False):
        bot_response = get_gpt_creator_response(user_input, my_info)
    else:
        bot_response = get_gpt_response(user_input, my_info, session_chat_history, lang)
        
    sentiment_analysis_result = perform_sentiment_analysis(user_input)
    log_sentiment(user_input, sentiment_analysis_result, session.get('logged_in_user'))

    session_chat_history.append({"role": "user", "parts": [user_input]})
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
    return redirect(url_for('index'))

@app.route('/set_language', methods=['POST'])
@login_required
def set_language():
    language = request.form.get('language')
    if language in TRANSLATIONS:
        session['language'] = language
    return jsonify({'status': 'success'})

# --- CREATOR TOOLS ROUTES ---
@app.route('/review_sentiment')
@login_required
def review_sentiment():
    if not is_creator_logged_in():
        return redirect(url_for('email_login'))
    
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
    sentiment_display_data.sort(key=lambda x: x['date'], reverse=True)
    return render_template('review_sentiment.html', sentiment_data=sentiment_display_data)

@app.route('/export_sentiment')
@login_required
def export_sentiment():
    if not is_creator_logged_in():
        return redirect(url_for('email_login'))
    
    sentiment_history = load_sentiment_history()
    csv_data = "Date,Timestamp,User Email,Sentiment Label,User Question\n"

    for day, data in sentiment_history.items():
        for interaction in data['interactions']:
            timestamp = interaction['timestamp']
            user_email = interaction['user_email']
            sentiment_label = interaction['sentiment']['label']
            user_input = interaction['user_input'].replace(',', '')
            csv_data += f"{day},{timestamp},{user_email},{sentiment_label},\"{user_input}\"\n"

    csv_file_path = os.path.join(app.root_path, 'sentiment_log.csv')
    with open(csv_file_path, 'w') as f:
        f.write(csv_data)
        
    return send_file(csv_file_path, as_attachment=True, download_name='sentiment_log.csv', mimetype='text/csv')

@app.route('/manage_knowledge', methods=['GET', 'POST'])
@login_required
def manage_knowledge():
    if not is_creator_logged_in():
        return redirect(url_for('email_login'))

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
                    "languages": request.form.get("skills_languages", "").split(',')
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
