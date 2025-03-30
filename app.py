from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import ptyprocess
import os
import json
import asyncio
from typing import Dict, Optional

app = FastAPI(title="Terminal Gateway")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active terminal sessions
terminal_sessions: Dict[str, ptyprocess.PtyProcess] = {}

@app.get("/")
async def read_root():
    return {"status": "healthy", "service": "Terminal Gateway"}

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    Handle WebSocket connections for terminal sessions.
    
    The WebSocket instance is automatically provided by FastAPI when a client connects
    to the "/ws/{session_id}" endpoint. FastAPI handles the WebSocket upgrade request
    and protocol negotiation under the hood.
    
    Args:
        websocket (WebSocket): FastAPI's WebSocket instance for the connection.
                             Provides methods for sending/receiving data.
        session_id (str): Unique identifier for the terminal session, extracted from URL path.
    """
    # Accept the WebSocket connection. This must be called before any send/receive operations
    await websocket.accept()
    
    try:
        # Create a new pseudo-terminal (PTY) process running bash
        # This creates a new terminal instance that we can read from and write to
        term = ptyprocess.PtyProcess.spawn(['/bin/bash'], dimensions=(24, 80))
        terminal_sessions[session_id] = term
        
        async def send_terminal_output():
            """
            Background task that continuously reads output from the terminal
            and sends it to the WebSocket client.
            """
            while True:
                try:
                    # Read any available output from the terminal
                    output = term.read()
                    if output:
                        # Send the output back to the client through WebSocket
                        # decode() converts bytes to string
                        await websocket.send_text(output.decode())
                except EOFError:
                    # Terminal process has ended
                    break
                except Exception as e:
                    print(f"Error reading terminal output: {e}")
                    break
                # Small delay to prevent CPU overuse
                await asyncio.sleep(0.01)

        # Start the output reader as a background task
        # This allows us to handle both reading and writing concurrently
        asyncio.create_task(send_terminal_output())

        # Main loop: Handle incoming messages from the WebSocket client
        while True:
            try:
                # Wait for and receive a message from the client
                data = await websocket.receive_text()
                command = json.loads(data)
                
                if command.get("type") == "input":
                    # Client sent terminal input
                    # Write the input to the terminal process
                    term.write(command["data"].encode())
                elif command.get("type") == "resize":
                    # Client requested terminal resize
                    # Update the terminal dimensions
                    rows = command.get("rows", 24)
                    cols = command.get("cols", 80)
                    term.setwinsize(rows, cols)
                
            except json.JSONDecodeError:
                # Client sent invalid JSON data
                await websocket.send_text(json.dumps({
                    "error": "Invalid JSON format"
                }))
            except Exception as e:
                print(f"Error processing command: {e}")
                break

    except WebSocketDisconnect:
        # Client disconnected
        print(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        print(f"Error in WebSocket connection: {e}")
    finally:
        # Clean up: Always terminate the terminal process and remove the session
        if session_id in terminal_sessions:
            term = terminal_sessions[session_id]
            term.terminate()
            del terminal_sessions[session_id]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True) 