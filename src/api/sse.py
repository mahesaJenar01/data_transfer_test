from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from asyncio import Queue, Event
import asyncio
import json
from typing import Dict, Any, Optional

from ..utils.logger import setup_logger

logger = setup_logger('sse', 'INFO')

router = APIRouter()

# Store connected clients
connected_clients = {}

# Shutdown event
shutdown_event = Event()

@router.on_event("shutdown")
async def shutdown_event_handler():
    """Handle application shutdown."""
    logger.info("SSE shutdown initiated, stopping background tasks")
    shutdown_event.set()
    # Give background tasks a moment to terminate gracefully
    await asyncio.sleep(1)

@router.get('/sse')
async def sse():
    """
    Endpoint for Server-Sent Events (SSE) to push real-time updates to clients
    """
    client_id = id(asyncio.current_task())
    queue = Queue()
    connected_clients[client_id] = queue
    
    logger.debug(f'Client {client_id} connected to SSE')
    
    async def event_generator():
        try:
            while True:
                # Send initial connection message
                if queue.empty():
                    yield "data: {\"type\": \"connected\"}\n\n"
                    
                # Wait for messages from the queue
                message = await queue.get()
                if message is None:
                    break
                    
                yield f"data: {message}\n\n"
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        finally:
            # Clean up when client disconnects
            if client_id in connected_clients:
                del connected_clients[client_id]
                logger.debug(f'Client {client_id} disconnected from SSE')
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'  # Prevents proxies from buffering the response
        }
    )

async def notify_clients(event_type: str, data: Optional[Dict[str, Any]] = None):
    """
    Notify all connected clients about an event
    
    Args:
        event_type (str): Type of event (e.g., 'config_updated')
        data (dict, optional): Additional data to send with the event
    """
    if not connected_clients:
        return
        
    event_data = {
        "type": event_type
    }
    
    if data:
        event_data.update(data)
        
    message = json.dumps(event_data)
    
    # Send to all connected clients
    for client_id, queue in list(connected_clients.items()):
        await queue.put(message)
    
    logger.debug(f'Notified {len(connected_clients)} clients: {event_type}')