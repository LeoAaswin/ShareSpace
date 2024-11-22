from flask import Flask, render_template, request, send_file, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import os
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import threading
import time
import json
import shutil

# Get the absolute path to the application directory
APP_ROOT = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['UPLOAD_FOLDER'] = os.path.join(APP_ROOT, 'static', 'uploads')  # Changed to static/uploads
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt'}

socketio = SocketIO(app)

# Create necessary directories
STATIC_DIR = os.path.join(APP_ROOT, 'static')
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Move any files from uploads to static/uploads if they exist
old_uploads = os.path.join(APP_ROOT, 'uploads')
if os.path.exists(old_uploads):
    for filename in os.listdir(old_uploads):
        old_path = os.path.join(old_uploads, filename)
        new_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.isfile(old_path):
            shutil.move(old_path, new_path)
    shutil.rmtree(old_uploads)

DATA_DIR = os.path.join(APP_ROOT, 'data')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

MESSAGES_FILE = os.path.join(DATA_DIR, 'message_history.json')
FILES_DB = os.path.join(DATA_DIR, 'files_db.json')

def load_messages():
    try:
        with open(MESSAGES_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_messages(messages):
    with open(MESSAGES_FILE, 'w') as f:
        json.dump(messages, f)

def load_files_db():
    try:
        with open(FILES_DB, 'r') as f:
            return json.load(f)
    except:
        return []

def save_files_db(files):
    with open(FILES_DB, 'w') as f:
        json.dump(files, f)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def cleanup_old_files():
    while True:
        now = datetime.now()
        # Clean up files
        files_db = load_files_db()
        current_files = []
        for file_info in files_db:
            file_time = datetime.fromisoformat(file_info['timestamp'])
            if now - file_time <= timedelta(days=7):
                # Verify file exists
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_info['filename'])
                if os.path.exists(filepath):
                    current_files.append(file_info)
            else:
                try:
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_info['filename'])
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    socketio.emit('file_removed', {'filename': file_info['filename']})
                except:
                    pass
        
        if len(current_files) != len(files_db):
            save_files_db(current_files)

        # Clean up messages
        messages = load_messages()
        current_messages = []
        changed = False
        for msg in messages:
            msg_time = datetime.fromisoformat(msg['timestamp'])
            if now - msg_time <= timedelta(days=7):
                current_messages.append(msg)
            else:
                changed = True
        
        if changed:
            save_messages(current_messages)
            socketio.emit('messages_updated')

        time.sleep(3600)  # Check every hour

# Initialize data files if they don't exist
if not os.path.exists(MESSAGES_FILE):
    with open(MESSAGES_FILE, 'w') as f:
        json.dump([], f)

if not os.path.exists(FILES_DB):
    with open(FILES_DB, 'w') as f:
        json.dump([], f)
else:
    # Verify and update existing file records
    files_db = load_files_db()
    updated_files = []
    for file_info in files_db:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_info['filename'])
        if os.path.exists(filepath):
            if 'url' not in file_info:
                file_info['url'] = f'/static/uploads/{file_info["filename"]}'
            updated_files.append(file_info)
    save_files_db(updated_files)

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

@app.route('/')
def index():
    # Get initial file list
    files_db = load_files_db()
    now = datetime.now()
    current_files = []
    
    for file_info in files_db:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_info['filename'])
        if os.path.exists(filepath):
            creation_time = datetime.fromisoformat(file_info['timestamp'])
            remaining_time = timedelta(days=7) - (now - creation_time)
            file_info['remaining_hours'] = int(remaining_time.total_seconds() / 3600)
            file_info['exists'] = True
            if 'url' not in file_info:
                file_info['url'] = f'/static/uploads/{file_info["filename"]}'
            current_files.append(file_info)
    
    # Update files_db if any files were missing
    if len(current_files) != len(files_db):
        save_files_db(current_files)
    
    return render_template('index.html', initial_files=current_files)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'files[]' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    files = request.files.getlist('files[]')
    uploaded_files = []
    files_db = load_files_db()
    
    for file in files:
        if file.filename == '':
            continue
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            base_name, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
                filename = f"{base_name}_{counter}{ext}"
                counter += 1
            
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            file_info = {
                'filename': filename,
                'size': os.path.getsize(filepath),
                'type': file.content_type,
                'timestamp': datetime.now().isoformat(),
                'url': f'/static/uploads/{filename}'  # Updated URL path
            }
            files_db.append(file_info)
            uploaded_files.append(file_info)
    
    if uploaded_files:
        save_files_db(files_db)
        socketio.emit('new_files', {'files': uploaded_files})
        return jsonify({'message': 'Files uploaded successfully', 'files': uploaded_files})
    
    return jsonify({'error': 'No valid files uploaded'}), 400

@app.route('/files')
def list_files():
    files_db = load_files_db()
    now = datetime.now()
    current_files = []
    
    for file_info in files_db:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_info['filename'])
        if os.path.exists(filepath):
            creation_time = datetime.fromisoformat(file_info['timestamp'])
            remaining_time = timedelta(days=7) - (now - creation_time)
            file_info['remaining_hours'] = int(remaining_time.total_seconds() / 3600)
            file_info['exists'] = True
            if 'url' not in file_info:
                file_info['url'] = f'/static/uploads/{file_info["filename"]}'
            current_files.append(file_info)
    
    # Update files_db if any files were missing
    if len(current_files) != len(files_db):
        save_files_db(current_files)
    
    return jsonify(current_files)

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        
        files_db = load_files_db()
        files_db = [f for f in files_db if f['filename'] != filename]
        save_files_db(files_db)
        
        socketio.emit('file_removed', {'filename': filename})
        return jsonify({'message': 'File deleted successfully'})
    except Exception as e:
        return jsonify({'error': f'Failed to delete file: {str(e)}'}), 400

@app.route('/delete_message/<message_id>', methods=['DELETE'])
def delete_message(message_id):
    try:
        messages = load_messages()
        messages = [m for m in messages if m['id'] != message_id]
        save_messages(messages)
        socketio.emit('message_deleted', {'id': message_id})
        return jsonify({'message': 'Message deleted successfully'})
    except Exception as e:
        return jsonify({'error': f'Failed to delete message: {str(e)}'}), 400

@socketio.on('send_message')
def handle_message(data):
    message = {
        'id': f"msg_{int(time.time() * 1000)}",
        'message': data['message'],
        'plainText': data.get('plainText', ''),  # Store plain text version
        'timestamp': datetime.now().isoformat()
    }
    messages = load_messages()
    messages.append(message)
    save_messages(messages)
    emit('new_message', message, broadcast=True)

@app.route('/messages')
def get_messages():
    messages = load_messages()
    return jsonify(messages)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
