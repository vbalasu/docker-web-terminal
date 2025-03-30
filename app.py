from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import ptyprocess
import os
import json
import logging
import re
from typing import Dict, Optional

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

# Store active terminal sessions
terminal_sessions: Dict[str, ptyprocess.PtyProcess] = {}

@app.route('/')
def index():
    """Serve the main index.html file"""
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    """Handle new WebSocket connections"""
    session_id = request.sid
    print(f"\n=== New WebSocket connection request for session: {session_id} ===")
    logger.info(f"New WebSocket connection request for session: {session_id}")
    
    # If there's an existing session, clean it up
    if session_id in terminal_sessions:
        try:
            term = terminal_sessions[session_id]
            term.terminate()
            del terminal_sessions[session_id]
            print(f"Cleaned up existing terminal session: {session_id}")
            logger.info(f"Cleaned up existing terminal session: {session_id}")
        except Exception as e:
            print(f"Error cleaning up existing session: {e}")
            logger.error(f"Error cleaning up existing session: {e}")
    
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
            ['/bin/bash'],  # Start bash without loading rc files
            dimensions=(24, 80),
            env=env
        )
        terminal_sessions[session_id] = term
        print(f"Terminal process created for session: {session_id}")
        logger.info(f"Terminal process created for session: {session_id}")
        
        def read_terminal():
            """Read and forward terminal output to WebSocket."""
            while True:
                try:
                    output = term.read()
                    if output:
                        decoded_output = decode_terminal_output(output)
                        print(f"Terminal output: {repr(decoded_output)}")
                        logger.info(f"Sending terminal output: {repr(decoded_output)}")
                        socketio.emit('terminal_output', {'data': output.decode('utf-8', errors='replace')}, room=session_id)
                except EOFError:
                    print(f"Terminal EOF for session: {session_id}")
                    logger.info(f"Terminal EOF for session: {session_id}")
                    break
                except Exception as e:
                    print(f"Error reading terminal output: {e}")
                    logger.error(f"Error reading terminal output: {e}")
                    break

        # Start reading terminal output in background
        import threading
        thread = threading.Thread(target=read_terminal)
        thread.daemon = True
        thread.start()
        print(f"Started terminal reader thread for session: {session_id}")
        logger.info(f"Started terminal reader thread for session: {session_id}")

    except Exception as e:
        print(f"Error in WebSocket connection: {e}")
        logger.error(f"Error in WebSocket connection: {e}")

@socketio.on('terminal_input')
def handle_terminal_input(data):
    """Handle terminal input from WebSocket"""
    session_id = request.sid
    print(f"\n=== Received terminal input for session: {session_id} ===")
    logger.info(f"Received terminal input for session: {session_id}")
    
    try:
        input_data = data.get('data', '')
        print(f"=== Raw input data: {repr(input_data)} ===")
        logger.info(f"Raw input data: {repr(input_data)}")
        
        if session_id in terminal_sessions:
            term = terminal_sessions[session_id]
            print(f"=== Writing to terminal: {repr(input_data)} ===")
            logger.info(f"Writing to terminal: {repr(input_data)}")
            term.write(input_data.encode('utf-8'))
            print("=== Write completed ===")
        else:
            print(f"=== No terminal session found for: {session_id} ===")
            logger.error(f"No terminal session found for: {session_id}")
            
    except Exception as e:
        print(f"=== Error processing terminal input: {e} ===")
        logger.error(f"Error processing terminal input: {e}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    session_id = request.sid
    print(f"=== WebSocket disconnected for session: {session_id} ===")
    logger.info(f"WebSocket disconnected for session: {session_id}")
    
    # Cleanup terminal session
    if session_id in terminal_sessions:
        try:
            term = terminal_sessions[session_id]
            term.terminate()
            del terminal_sessions[session_id]
            print(f"=== Cleaned up terminal session: {session_id} ===")
            logger.info(f"Cleaned up terminal session: {session_id}")
        except Exception as e:
            print(f"=== Error cleaning up terminal session: {e} ===")
            logger.error(f"Error cleaning up terminal session: {e}")

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8000, debug=True) 
