# Terminal Gateway Server

A FastAPI-based WebSocket server that provides terminal access through a web interface.

## Features

- WebSocket-based real-time terminal communication
- Support for multiple terminal sessions
- Terminal resizing capability
- Clean session management and cleanup

## Requirements

- Python 3.8+
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

## WebSocket API

Connect to the WebSocket endpoint: `ws://localhost:8000/ws/{session_id}`

### Message Format

Send commands to the terminal in JSON format:

1. Terminal Input:
```json
{
    "type": "input",
    "data": "ls -la\n"
}
```

2. Resize Terminal:
```json
{
    "type": "resize",
    "rows": 24,
    "cols": 80
}
```

### Response

Terminal output is sent as text through the WebSocket connection.

## Security Considerations

- In production, configure proper CORS settings
- Implement authentication and authorization
- Use secure WebSocket connections (wss://) 