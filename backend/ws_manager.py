"""WebSocket Connection and Real-Time Event Hub for NOVA."""

import json
import logging
from typing import Any, Dict, List, Set
from fastapi import WebSocket

logger = logging.getLogger("nova.ws")


class ConnectionManager:
    """Manages active WebSocket connections from dashboard and paired clients."""

    def __init__(self):
        # Active connections: client_id -> Set[WebSocket]
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, client_id: str = "anonymous") -> None:
        """Accept connection and register under client_id."""
        await websocket.accept()
        if client_id not in self.active_connections:
            self.active_connections[client_id] = set()
        self.active_connections[client_id].add(websocket)
        logger.info(f"WebSocket client connected: {client_id}")

    def disconnect(self, websocket: WebSocket, client_id: str = "anonymous") -> None:
        """Remove connection upon disconnect."""
        if client_id in self.active_connections:
            self.active_connections[client_id].discard(websocket)
            if not self.active_connections[client_id]:
                del self.active_connections[client_id]
        logger.info(f"WebSocket client disconnected: {client_id}")

    async def broadcast(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Broadcast JSON message to all active WebSocket connections."""
        message = json.dumps({"event": event_type, "data": payload})
        stale_connections = []

        for cid, sockets in list(self.active_connections.items()):
            for ws in list(sockets):
                try:
                    await ws.send_text(message)
                except Exception as e:
                    logger.debug(f"Failed to send to client {cid}: {e}")
                    stale_connections.append((cid, ws))

        # Cleanup closed sockets
        for cid, ws in stale_connections:
            self.disconnect(ws, cid)

    async def send_personal(self, client_id: str, event_type: str, payload: Dict[str, Any]) -> bool:
        """Send message directly to a specific client_id."""
        sockets = self.active_connections.get(client_id, set())
        if not sockets:
            return False

        message = json.dumps({"event": event_type, "data": payload})
        sent = False
        for ws in list(sockets):
            try:
                await ws.send_text(message)
                sent = True
            except Exception:
                self.disconnect(ws, client_id)
        return sent


ws_hub = ConnectionManager()
