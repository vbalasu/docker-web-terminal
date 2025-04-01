# Web Terminal with Docker

A Flask-based web application that provides terminal access to a Docker container through a web interface.

## Features

- WebSocket-based real-time terminal communication using Flask-SocketIO
- Docker container integration (Python 3.12.9 container)
- Terminal session management with automatic cleanup
- ANSI color support in the terminal output
- Responsive web interface with Bootstrap styling

## Requirements

- Python 3.8+
- Docker
- Virtual environment (recommended)

## Setup

1. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Server

Start the server with:
```bash
python app.py
```

The server will run on `http://localhost:8000` by default.

## Web Interface

The web interface provides:
- A terminal output area with monospace font
- A command input field
- Connection status indicator
- Support for ANSI color codes in terminal output

## Technical Details

- Uses Flask-SocketIO for WebSocket communication
- Runs commands in a Docker container with resource limits:
  - CPU: 0.5 cores
  - Memory: 100MB
- Container image: python:3.12.9-bookworm
- Terminal dimensions: 24x80 characters
- Supports real-time terminal output with ANSI color codes

## Security Considerations

- In production, configure proper CORS settings
- Implement authentication and authorization
- Use secure WebSocket connections (wss://)
- Consider container security best practices 