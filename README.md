# Real-Time File and Text Sharing Web App

A web application for sharing files and text messages in real-time within the same network.

## Features

- Real-time text messaging
- File upload and sharing
- Instant file notifications
- Modern and responsive UI
- Local network file sharing

## Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python app.py
```

3. Access the application:
- Open your web browser
- Navigate to `http://localhost:5000` or `http://<your-local-ip>:5000`
- Share the URL with others on the same network to start sharing files and messages

## Usage

### File Sharing
- Click the file input to select a file
- Click "Upload" to share the file
- Files appear in the shared files list
- Click "Download" next to any file to download it

### Text Sharing
- Type your message in the text input
- Click "Send" or press Enter to share the message
- Messages appear in real-time for all connected users

## Security Note

This application is designed for use within trusted local networks only. Do not expose it to the public internet without implementing proper security measures.
