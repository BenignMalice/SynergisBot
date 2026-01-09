"""
TelegramMoneyBot Phone Control System - Command Hub

Central service that routes commands from phone Custom GPT to desktop agent.
Runs on localhost:8001, exposed via ngrok for phone access.
"""

from fastapi import FastAPI, HTTPException, Header, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import asyncio
import secrets
import logging
from datetime import datetime
import json
import uuid
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="TelegramMoneyBot Phone Control Hub",
    description="Command routing hub between phone Custom GPT and desktop trading agent",
    version="1.0.0"
)

# CORS for phone GPT
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Authentication tokens from .env file
PHONE_TOKEN = os.getenv("PHONE_BEARER_TOKEN", "phone_control_bearer_token_2025_v1_secure")
AGENT_SECRET = os.getenv("AGENT_SECRET", "phone_control_bearer_token_2025_v1_secure")

logger.info(f"🔐 Phone Bearer Token: {PHONE_TOKEN}")
logger.info(f"🔐 Agent Secret: {AGENT_SECRET}")

# ============================================================================
# STATE MANAGEMENT
# ============================================================================

class CommandState:
    """Manages active commands and agent connections"""
    
    def __init__(self):
        self.agent_ws: Optional[WebSocket] = None
        self.agent_connected: bool = False
        self.pending_commands: Dict[str, asyncio.Future] = {}
        self.command_history: List[Dict[str, Any]] = []
        
    def is_agent_online(self) -> bool:
        return self.agent_connected and self.agent_ws is not None
    
    def add_command(self, command_id: str) -> asyncio.Future:
        """Register a new command and return a future for its result"""
        future = asyncio.Future()
        self.pending_commands[command_id] = future
        logger.info(f"📝 Command {command_id} registered, awaiting result")
        return future
    
    def complete_command(self, command_id: str, result: Dict[str, Any]):
        """Mark command as complete with result"""
        if command_id in self.pending_commands:
            future = self.pending_commands[command_id]
            if not future.done():
                future.set_result(result)
                logger.info(f"✅ Command {command_id} completed")
            del self.pending_commands[command_id]
        else:
            logger.warning(f"⚠️ Received result for unknown command: {command_id}")
    
    def fail_command(self, command_id: str, error: str):
        """Mark command as failed"""
        if command_id in self.pending_commands:
            future = self.pending_commands[command_id]
            if not future.done():
                future.set_exception(Exception(error))
                logger.error(f"❌ Command {command_id} failed: {error}")
            del self.pending_commands[command_id]
    
    def log_command(self, command_id: str, tool: str, args: Dict, result: Optional[Dict] = None, error: Optional[str] = None):
        """Store command in history"""
        entry = {
            "command_id": command_id,
            "tool": tool,
            "arguments": args,
            "timestamp": datetime.utcnow().isoformat(),
            "result": result,
            "error": error,
            "success": error is None
        }
        self.command_history.append(entry)
        # Keep only last 100 commands
        if len(self.command_history) > 100:
            self.command_history = self.command_history[-100:]

state = CommandState()

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class DispatchRequest(BaseModel):
    """Command from phone Custom GPT"""
    tool: str  # e.g., "moneybot.analyse_symbol"
    arguments: Dict[str, Any]
    timeout: Optional[int] = 30  # seconds

class DispatchResponse(BaseModel):
    """Response to phone Custom GPT"""
    command_id: str
    status: str  # "success" | "error" | "timeout"
    summary: str  # Human-readable summary
    data: Optional[Dict[str, Any]] = None  # Structured data for follow-ups
    error: Optional[str] = None
    execution_time: float  # seconds

class AgentMessage(BaseModel):
    """Message from desktop agent"""
    command_id: str
    status: str  # "in_progress" | "completed" | "error"
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# ============================================================================
# AUTHENTICATION
# ============================================================================

def verify_phone_token(authorization: Optional[str] = Header(None)) -> bool:
    """Verify phone Custom GPT bearer token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")
    
    token = authorization.replace("Bearer ", "")
    if token != PHONE_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")
    
    return True

# ============================================================================
# PHONE API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "TelegramMoneyBot Phone Control Hub",
        "status": "online",
        "agent_connected": state.is_agent_online(),
        "pending_commands": len(state.pending_commands)
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "hub": "healthy",
        "agent_status": "online" if state.is_agent_online() else "offline",
        "pending_commands": len(state.pending_commands),
        "total_commands_processed": len(state.command_history),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/dispatch", response_model=DispatchResponse)
async def dispatch_command(
    request: DispatchRequest,
    authorized: bool = Header(None, depends=verify_phone_token)
):
    """
    Main endpoint for phone Custom GPT to dispatch commands
    
    Flow:
    1. Phone sends command with tool name and arguments
    2. Hub generates unique command_id
    3. Hub forwards to desktop agent via WebSocket
    4. Hub waits for result (with timeout)
    5. Hub returns result to phone
    """
    start_time = datetime.utcnow()
    command_id = str(uuid.uuid4())
    
    logger.info(f"📱 Received command from phone: {request.tool}")
    logger.debug(f"   Command ID: {command_id}")
    logger.debug(f"   Arguments: {request.arguments}")
    
    # Check if agent is connected
    if not state.is_agent_online():
        error_msg = "Desktop agent is offline. Please ensure the agent is running on your computer."
        logger.error(f"❌ {error_msg}")
        state.log_command(command_id, request.tool, request.arguments, error=error_msg)
        
        return DispatchResponse(
            command_id=command_id,
            status="error",
            summary="❌ Desktop agent offline",
            error=error_msg,
            execution_time=0.0
        )
    
    # Register command and create future for result
    result_future = state.add_command(command_id)
    
    # Send command to agent
    command_payload = {
        "command_id": command_id,
        "tool": request.tool,
        "arguments": request.arguments,
        "timeout": request.timeout
    }
    
    try:
        await state.agent_ws.send_json(command_payload)
        logger.info(f"📤 Forwarded command {command_id} to desktop agent")
        
        # Wait for result with timeout
        try:
            result = await asyncio.wait_for(result_future, timeout=request.timeout)
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            logger.info(f"✅ Command {command_id} completed in {execution_time:.2f}s")
            state.log_command(command_id, request.tool, request.arguments, result=result)
            
            return DispatchResponse(
                command_id=command_id,
                status="success",
                summary=result.get("summary", "Command completed"),
                data=result.get("data"),
                execution_time=execution_time
            )
            
        except asyncio.TimeoutError:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Command timed out after {request.timeout}s. The agent may still be processing it."
            
            logger.warning(f"⏱️ Command {command_id} timed out")
            state.fail_command(command_id, error_msg)
            state.log_command(command_id, request.tool, request.arguments, error=error_msg)
            
            return DispatchResponse(
                command_id=command_id,
                status="timeout",
                summary="⏱️ Command timed out",
                error=error_msg,
                execution_time=execution_time
            )
            
    except Exception as e:
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        error_msg = f"Failed to send command to agent: {str(e)}"
        
        logger.error(f"❌ {error_msg}")
        state.fail_command(command_id, error_msg)
        state.log_command(command_id, request.tool, request.arguments, error=error_msg)
        
        return DispatchResponse(
            command_id=command_id,
            status="error",
            summary="❌ Command failed",
            error=error_msg,
            execution_time=execution_time
        )

@app.get("/history")
async def get_command_history(
    limit: int = 10,
    authorized: bool = Header(None, depends=verify_phone_token)
):
    """Get recent command history"""
    history = state.command_history[-limit:]
    return {
        "total": len(state.command_history),
        "showing": len(history),
        "commands": history
    }

# ============================================================================
# DESKTOP AGENT WEBSOCKET
# ============================================================================

@app.websocket("/agent/connect")
async def agent_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for desktop agent to connect and receive commands
    
    Flow:
    1. Agent connects with secret authentication
    2. Agent stays connected, receives commands
    3. Agent processes commands and sends results back
    4. If agent disconnects, all pending commands fail
    """
    await websocket.accept()
    logger.info("🔌 Desktop agent attempting to connect...")
    
    # Authenticate agent
    try:
        auth_msg = await websocket.receive_json()
        if auth_msg.get("secret") != AGENT_SECRET:
            await websocket.send_json({"status": "error", "message": "Invalid secret"})
            await websocket.close()
            logger.error("❌ Agent authentication failed")
            return
        
        await websocket.send_json({"type": "auth_success", "message": "Welcome, agent!"})
        logger.info("✅ Desktop agent authenticated and connected")
        
    except Exception as e:
        logger.error(f"❌ Agent authentication error: {e}")
        await websocket.close()
        return
    
    # Mark agent as connected
    state.agent_ws = websocket
    state.agent_connected = True
    
    try:
        # Keep connection alive and handle agent messages
        while True:
            message = await websocket.receive_json()
            
            # Agent sends results/updates for commands
            command_id = message.get("command_id")
            status = message.get("status")
            
            if status == "completed":
                # Command completed successfully
                result = {
                    "summary": message.get("summary", "Command completed"),
                    "data": message.get("data")
                }
                state.complete_command(command_id, result)
                logger.info(f"✅ Agent completed command {command_id}")
                
            elif status == "error":
                # Command failed
                error = message.get("error", "Unknown error")
                state.fail_command(command_id, error)
                logger.error(f"❌ Agent reported error for {command_id}: {error}")
                
            elif status == "in_progress":
                # Progress update (optional, for logging)
                logger.debug(f"⏳ Command {command_id}: {message.get('message')}")
            else:
                # Unknown status - log warning but handle gracefully
                message_type = message.get("type")
                logger.warning(f"Unknown message type from agent: {message_type} - status: {status}")
                # Try to extract command_id and handle as completed if present
                if command_id:
                    logger.info(f"Attempting to complete command {command_id} with unknown status")
                    result = {
                        "summary": message.get("summary", "Command completed"),
                        "data": message.get("data")
                    }
                    state.complete_command(command_id, result)
            
    except WebSocketDisconnect:
        logger.warning("🔌 Desktop agent disconnected")
    except Exception as e:
        logger.error(f"❌ WebSocket error: {e}")
    finally:
        # Clean up on disconnect
        state.agent_connected = False
        state.agent_ws = None
        
        # Fail all pending commands
        for command_id in list(state.pending_commands.keys()):
            state.fail_command(command_id, "Agent disconnected")
        
        logger.info("🔌 Agent connection closed")

# ============================================================================
# STARTUP
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Print important info on startup"""
    phone_hub_port = int(os.getenv("PHONE_HUB_PORT", "8002"))
    logger.info("=" * 70)
    logger.info("🚀 TelegramMoneyBot Phone Control Hub - STARTING")
    logger.info("=" * 70)
    logger.info(f"📱 Phone API: http://localhost:{phone_hub_port}/dispatch")
    logger.info(f"🔌 Agent WebSocket: ws://localhost:{phone_hub_port}/agent/connect")
    logger.info(f"")
    logger.info(f"🔐 IMPORTANT: Save these tokens securely!")
    logger.info(f"   Phone Token (for Custom GPT): {PHONE_TOKEN}")
    logger.info(f"   Agent Secret (for desktop_agent.py): {AGENT_SECRET}")
    logger.info(f"")
    logger.info(f"📝 Next steps:")
    logger.info(f"   1. Run: ngrok http {phone_hub_port}")
    logger.info(f"   2. Copy ngrok URL to Custom GPT Actions")
    logger.info(f"   3. Run: python desktop_agent.py")
    logger.info("=" * 70)

if __name__ == "__main__":
    import uvicorn
    # FIX: Use port 8002 by default to avoid conflict with DTMS API server (port 8001)
    phone_hub_port = int(os.getenv("PHONE_HUB_PORT", "8002"))
    uvicorn.run(app, host="0.0.0.0", port=phone_hub_port)

