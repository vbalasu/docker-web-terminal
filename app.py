from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit
import ptyprocess
import os
import json
import logging
import re
import time
from typing import Dict, Optional
from datetime import datetime, timedelta

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
SESSION_TIMEOUT_MINUTES = 15

def decode_terminal_output(output: bytes) -> str:
    """Decode terminal output to readable text by removing ANSI codes and special characters."""
    # Decode bytes to string
    text = output.decode('utf-8', errors='replace')
    
    # Remove ANSI escape codes
    ansi_escape = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
    text = ansi_escape.sub('', text)
    
    # Replace special characters with readable equivalents
    text = text.replace('\r', '')
    text = text.replace('\x08', '')  # Backspace
    text = text.replace('\x1b[?2004h', '')  # Bracketed paste mode
    text = text.replace('\x1b[?2004l', '')  # End bracketed paste mode
    text = text.replace('\x1b[J', '')  # Clear screen
    text = text.replace('\x1b[K', '')  # Clear line
    
    return text

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Store active terminal sessions with last activity timestamp
terminal_sessions: Dict[str, Dict] = {}

@app.route('/')
def index():
    """Serve the main index.html file"""
    return render_template('index.html')

def cleanup_inactive_sessions():
    """Clean up sessions that have been inactive for more than SESSION_TIMEOUT_MINUTES."""
    current_time = datetime.now()
    inactive_sessions = []
    
    for session_id, session_data in terminal_sessions.items():
        last_activity = session_data.get('last_activity')
        if last_activity and (current_time - last_activity) > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            inactive_sessions.append(session_id)
    
    for session_id in inactive_sessions:
        cleanup_session(session_id)

def cleanup_session(session_id: str):
    """Clean up a specific terminal session."""
    if session_id in terminal_sessions:
        try:
            session_data = terminal_sessions[session_id]
            term = session_data.get('term')
            if term:
                term.terminate()
                # Force kill after 5 seconds if still running
                time.sleep(5)
                if term.isalive():
                    term.kill()
            del terminal_sessions[session_id]
            logger.info(f"Cleaned up terminal session: {session_id}")
        except Exception as e:
            logger.error(f"Error cleaning up terminal session {session_id}: {e}")

@socketio.on('connect')
def handle_connect():
    """Handle new WebSocket connections"""
    session_id = request.sid
    logger.info(f"New WebSocket connection request for session: {session_id}")
    
    # Clean up any existing session for this client
    cleanup_session(session_id)
    
    try:
        # Create a new terminal process with minimal environment
        env = {
            "TERM": "xterm-256color",
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "USER": os.environ.get("USER", ""),
            "SHELL": "/bin/bash"
        }
        
        term = ptyprocess.PtyProcess.spawn(
            ['docker', 'run', '-ti', '--rm', '--cpus=0.5', '--memory=100m', 'python:3.12.9-bookworm'],
            dimensions=(24, 80),
            env=env
        )
        
        # Store session with timestamp
        terminal_sessions[session_id] = {
            'term': term,
            'last_activity': datetime.now()
        }
        
        logger.info(f"Terminal process created for session: {session_id}")
        
        def read_terminal():
            """Read and forward terminal output to WebSocket."""
            while True:
                try:
                    output = term.read()
                    if output:
                        decoded_output = decode_terminal_output(output)
                        logger.info(f"Sending terminal output: {repr(decoded_output)}")
                        socketio.emit('terminal_output', {'data': output.decode('utf-8', errors='replace')}, room=session_id)
                except EOFError:
                    logger.info(f"Terminal EOF for session: {session_id}")
                    break
                except Exception as e:
                    logger.error(f"Error reading terminal output: {e}")
                    break

        # Start reading terminal output in background
        import threading
        thread = threading.Thread(target=read_terminal)
        thread.daemon = True
        thread.start()
        logger.info(f"Started terminal reader thread for session: {session_id}")

    except Exception as e:
        logger.error(f"Error in WebSocket connection: {e}")

@socketio.on('terminal_input')
def handle_terminal_input(data):
    """Handle terminal input from WebSocket"""
    session_id = request.sid
    logger.info(f"Received terminal input for session: {session_id}")
    
    try:
        input_data = data.get('data', '')
        logger.info(f"Raw input data: {repr(input_data)}")
        
        if session_id in terminal_sessions:
            session_data = terminal_sessions[session_id]
            term = session_data.get('term')
            if term:
                # Update last activity timestamp
                session_data['last_activity'] = datetime.now()
                logger.info(f"Writing to terminal: {repr(input_data)}")
                term.write(input_data.encode('utf-8'))
        else:
            logger.error(f"No terminal session found for: {session_id}")
            
    except Exception as e:
        logger.error(f"Error processing terminal input: {e}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    session_id = request.sid
    logger.info(f"WebSocket disconnected for session: {session_id}")
    cleanup_session(session_id)

# Start a background thread to periodically check for inactive sessions
def check_inactive_sessions():
    while True:
        cleanup_inactive_sessions()
        time.sleep(60)  # Check every minute

import threading
inactivity_checker = threading.Thread(target=check_inactive_sessions)
inactivity_checker.daemon = True
inactivity_checker.start()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8000, debug=True) 
