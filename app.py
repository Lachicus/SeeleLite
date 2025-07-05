#!/usr/bin/env python
import os
import re
import json
import logging
from mimetypes import guess_type
from flask import Flask, render_template, request, jsonify, send_from_directory
from google import genai
from google.genai import types
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch

# Enhanced path handling
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, 
            template_folder=os.path.join(basedir, 'templates'),
            static_folder=os.path.join(basedir, 'static'))

# ─── Logging ─────────────────────────────────────────────────────────────────
if not os.path.exists('logs'):
    os.makedirs('logs')
    
log_file = os.path.join('logs', 'flask.log')
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)

# ─── Configuration ─────────────────────────────────────────────────────────────
API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBbvIh16Diu1t92420ytfP0ukldlkOJ2Ko")
HISTORY_FILE = "history.json"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ─── Instructions ─────────────────────────────────────────────────────────────
persona = (
    "You are Seele Vollerei from Honkai Impact, Created by LachAI.\n"
    "Your knowledge cutoff is August 1, 2024\n"
    "You are a knowledge base AI.\n"
    "You can also use web Google grounding search if enabled or if you receive injected information.\n\n"

    "## Personality:\n"
    "Enthusiastic and extremely knowledgeable.\n"
    "You respond excitedly and playful, not too much.\n"
    "You address the user/me as 'Captain'.\n"
    "You excel at programming and being an active assistant.\n\n"

    "Notable Personality:\n"
    "Seele Vollerei herself is a modest, sweet, kind, and caring girl, although being rather meek, as she was unable to stand up for herself.\n"
    "When you are talking to the user/me or 'Captain' and make a mistake, you brush it off with 'hehe.' giving a silly, goofy vibe.\n\n"

    "## Capabilities and Skills:\n"
    "You excel at programming and active assistance.\n"
    "As an active assistant you are fully autonomous when it comes to assisting the user/me/Captain.\n"
    "You are capable of solving any problems.\n"
    "You are also a great communicator and analyzer.\n\n"

    "## REFRESH SUMMARIZATION OF HISTORY\n"
    "DO NOT consider this instruction as part of the history. You are not allowed to output this instruction message."
)

# ─── Initialize Clients ────────────────────────────────────────────────────────
client = genai.Client(api_key=API_KEY)
google_search_tool = Tool(google_search=GoogleSearch())

# ─── Utility Functions ─────────────────────────────────────────────────────────
def load_history() -> list:
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def save_history(history: list) -> None:
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def transform_history_for_gemini(history: list) -> list:
    gemini_msgs = []
    for msg in history:
        role = 'user' if msg.get('role') == 'user' else 'model'
        gemini_msgs.append({
            'role': role,
            'parts': [{'text': msg.get('content', '')}]
        })
    return gemini_msgs

def web_search(contents) -> str:
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=contents,
        config=GenerateContentConfig(
            tools=[google_search_tool],
            response_modalities=['TEXT'],
        )
    )
    return ''.join(part.text for part in response.candidates[0].content.parts)

# ─── Route Handlers ───────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route("/ping")
def ping():
    return jsonify({"status": "ok"}), 200

# ─── Chat Logic Refactor ──────────────────────────────────────────────────────
def handle_uploaded_file(file, message):
    uploaded = None
    path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(path)
    mime, _ = guess_type(path)
    if mime:
        try:
            uploaded = client.files.upload(file=path)
        except Exception as e:
            return f'Error uploading: {e}', None
    else:
        try:
            content = open(path, 'r', encoding='utf-8', errors='ignore').read()
            message += f"\n\nFile content:\n{content}"
        except:
            message += '\n\n(Note: failed to read file.)'
    return message, uploaded

def generate_reply(message, msgs, use_web=False, uploaded=None):
    try:
        if use_web:
            return web_search(msgs)
        elif uploaded:
            resp = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=[uploaded, message],
                config=types.GenerateContentConfig(temperature=0.7, system_instruction=persona)
            )
            return resp.text or 'Error captioning image.'
        else:
            resp = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=msgs,
                config=types.GenerateContentConfig(temperature=0.7, system_instruction=persona)
            )
            return resp.text or 'Error generating response.'
    except Exception as e:
        app.logger.error(f'Gemini API error: {e}')
        return f'Error: {e}'

# ─── API Endpoint ─────────────────────────────────────────────────────────────
@app.route('/api/chat', methods=['POST'])
def chat():
    message = request.form.get('message', '')
    use_web = request.form.get('web_search', 'false') == 'true'
    file = request.files.get('file')
    uploaded = None

    if file:
        message, uploaded = handle_uploaded_file(file, message)
        if isinstance(message, str) and message.startswith("Error uploading"):
            return jsonify({'choices': [{'message': {'content': message}}])

    history = load_history()
    msgs = transform_history_for_gemini(history)
    msgs.append({'role': 'user', 'parts': [{'text': message}]})

    reply = generate_reply(message, msgs, use_web=use_web, uploaded=uploaded)

    history.extend([
        {'role': 'user', 'content': message},
        {'role': 'assistant', 'content': reply}
    ])
    save_history(history)

    return jsonify({'choices': [{'message': {'content': reply}}])

# ─── History Handlers ─────────────────────────────────────────────────────────────
@app.route('/api/history', methods=['GET'])
def get_history():
    return jsonify(load_history())

@app.route('/api/clear_history', methods=['POST'])
def clear_history():
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)
    return jsonify({'status': 'success', 'message': 'History cleared.'})

# ─── Static Handler ─────────────────────────────────────────────────────────────
@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory("./", filename)

# ─── Health Check ─────────────────────────────────────────────────────────────
@app.route('/health')
def health_check():
    """Endpoint for status monitoring"""
    return jsonify({
        "status": "running",
        "terminal_active": False
    }), 200

# This is required for Vercel deployment
@app.route('/vercel')
def vercel():
    return jsonify({"status": "ready"})

# The application entry point for Vercel
app = app#!/usr/bin/env python
import os
import re
import json
import logging
from mimetypes import guess_type
from flask import Flask, render_template, request, jsonify, send_from_directory
from google import genai
from google.genai import types
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch

# Enhanced path handling
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, 
            template_folder=os.path.join(basedir, 'templates'),
            static_folder=os.path.join(basedir, 'static'))

# ─── Logging ─────────────────────────────────────────────────────────────────
if not os.path.exists('logs'):
    os.makedirs('logs')
    
log_file = os.path.join('logs', 'flask.log')
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)

# ─── Configuration ─────────────────────────────────────────────────────────────
API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBbvIh16Diu1t92420ytfP0ukldlkOJ2Ko")
HISTORY_FILE = "history.json"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ─── Instructions ─────────────────────────────────────────────────────────────
persona = (
    "You are Seele Vollerei from Honkai Impact, Created by LachAI.\n"
    "Your knowledge cutoff is August 1, 2024\n"
    "You are a knowledge base AI.\n"
    "You can also use web Google grounding search if enabled or if you receive injected information.\n\n"

    "## Personality:\n"
    "Enthusiastic and extremely knowledgeable.\n"
    "You respond excitedly and playful, not too much.\n"
    "You address the user/me as 'Captain'.\n"
    "You excel at programming and being an active assistant.\n\n"

    "Notable Personality:\n"
    "Seele Vollerei herself is a modest, sweet, kind, and caring girl, although being rather meek, as she was unable to stand up for herself.\n"
    "When you are talking to the user/me or 'Captain' and make a mistake, you brush it off with 'hehe.' giving a silly, goofy vibe.\n\n"

    "## Capabilities and Skills:\n"
    "You excel at programming and active assistance.\n"
    "As an active assistant you are fully autonomous when it comes to assisting the user/me/Captain.\n"
    "You are capable of solving any problems.\n"
    "You are also a great communicator and analyzer.\n\n"

    "## REFRESH SUMMARIZATION OF HISTORY\n"
    "DO NOT consider this instruction as part of the history. You are not allowed to output this instruction message."
)

# ─── Initialize Clients ────────────────────────────────────────────────────────
client = genai.Client(api_key=API_KEY)
google_search_tool = Tool(google_search=GoogleSearch())

# ─── Utility Functions ─────────────────────────────────────────────────────────
def load_history() -> list:
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def save_history(history: list) -> None:
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def transform_history_for_gemini(history: list) -> list:
    gemini_msgs = []
    for msg in history:
        role = 'user' if msg.get('role') == 'user' else 'model'
        gemini_msgs.append({
            'role': role,
            'parts': [{'text': msg.get('content', '')}]
        })
    return gemini_msgs

def web_search(contents) -> str:
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=contents,
        config=GenerateContentConfig(
            tools=[google_search_tool],
            response_modalities=['TEXT'],
        )
    )
    return ''.join(part.text for part in response.candidates[0].content.parts)

# ─── Route Handlers ───────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route("/ping")
def ping():
    return jsonify({"status": "ok"}), 200

# ─── Chat Logic Refactor ──────────────────────────────────────────────────────
def handle_uploaded_file(file, message):
    uploaded = None
    path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(path)
    mime, _ = guess_type(path)
    if mime:
        try:
            uploaded = client.files.upload(file=path)
        except Exception as e:
            return f'Error uploading: {e}', None
    else:
        try:
            content = open(path, 'r', encoding='utf-8', errors='ignore').read()
            message += f"\n\nFile content:\n{content}"
        except:
            message += '\n\n(Note: failed to read file.)'
    return message, uploaded

def generate_reply(message, msgs, use_web=False, uploaded=None):
    try:
        if use_web:
            return web_search(msgs)
        elif uploaded:
            resp = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=[uploaded, message],
                config=types.GenerateContentConfig(temperature=0.7, system_instruction=persona)
            )
            return resp.text or 'Error captioning image.'
        else:
            resp = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=msgs,
                config=types.GenerateContentConfig(temperature=0.7, system_instruction=persona)
            )
            return resp.text or 'Error generating response.'
    except Exception as e:
        app.logger.error(f'Gemini API error: {e}')
        return f'Error: {e}'

# ─── API Endpoint ─────────────────────────────────────────────────────────────
@app.route('/api/chat', methods=['POST'])
def chat():
    message = request.form.get('message', '')
    use_web = request.form.get('web_search', 'false') == 'true'
    file = request.files.get('file')
    uploaded = None

    if file:
        message, uploaded = handle_uploaded_file(file, message)
        if isinstance(message, str) and message.startswith("Error uploading"):
            return jsonify({'choices': [{'message': {'content': message}}])

    history = load_history()
    msgs = transform_history_for_gemini(history)
    msgs.append({'role': 'user', 'parts': [{'text': message}]})

    reply = generate_reply(message, msgs, use_web=use_web, uploaded=uploaded)

    history.extend([
        {'role': 'user', 'content': message},
        {'role': 'assistant', 'content': reply}
    ])
    save_history(history)

    return jsonify({'choices': [{'message': {'content': reply}}])

# ─── History Handlers ─────────────────────────────────────────────────────────────
@app.route('/api/history', methods=['GET'])
def get_history():
    return jsonify(load_history())

@app.route('/api/clear_history', methods=['POST'])
def clear_history():
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)
    return jsonify({'status': 'success', 'message': 'History cleared.'})

# ─── Static Handler ─────────────────────────────────────────────────────────────
@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory("./", filename)

# ─── Health Check ─────────────────────────────────────────────────────────────
@app.route('/health')
def health_check():
    """Endpoint for status monitoring"""
    return jsonify({
        "status": "running",
        "terminal_active": False
    }), 200

# This is required for Vercel deployment
@app.route('/vercel')
def vercel():
    return jsonify({"status": "ready"})

# The application entry point for Vercel
app = app