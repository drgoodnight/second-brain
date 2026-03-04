#!/usr/bin/env python3
"""
SimpleX ↔ n8n Bridge v2.1 with Whisper Integration (FIXED)
Bidirectional bridge with media support, persistent connections, and voice transcription.

FIXES in v2.1:
- Voice message file info is now correctly read from chatItem.file (not msgContent.voice)
- Auto-accepts files via /fr command when fileStatus.type == "rcvInvitation"
- Waits for file download completion before transcription
- Polls for file status changes after accepting

Features:
- Voice transcription via Whisper API
- Image and file message support
- Persistent WebSocket connection with auto-reconnect
- Bidirectional messaging (SimpleX ↔ n8n)
- HTTP endpoints for health checks, metrics, and message sending
- Proper logging with rotation
- Metrics collection
- Rate limiting
- Webhook authentication
- State cleanup
- Group chat support
- Type hints throughout
"""

import json
import time
import os
import signal
import sys
import hmac
import hashlib
import logging
import mimetypes
from logging.handlers import RotatingFileHandler
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, List, Any, Set
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlparse
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import socket

try:
    import websocket
except ImportError:
    print("ERROR: websocket-client not installed. Run: pip install websocket-client")
    sys.exit(1)


# ============================================================
# Configuration
# ============================================================

@dataclass
class BridgeConfig:
    """Bridge configuration loaded from environment variables"""
    ws_url: str
    webhook_url: str
    whisper_api_url: str = ""
    state_file: str = "/app/scripts/state/simplex_last_seen.json"
    poll_seconds: float = 2.0
    ws_timeout: float = 10.0
    ws_reconnect_delay: float = 5.0
    debug_ws_events: bool = False
    webhook_max_retries: int = 3
    webhook_retry_backoff: float = 2.0
    webhook_secret: str = ""
    health_check_on_start: bool = True
    http_port: int = 8080
    http_bind: str = "0.0.0.0"
    log_level: str = "INFO"
    log_file: str = "/app/logs/bridge.log"
    log_max_bytes: int = 10 * 1024 * 1024  # 10MB
    log_backup_count: int = 5
    rate_limit_per_minute: int = 20
    state_cleanup_max_contacts: int = 1000
    enable_metrics: bool = True
    enable_group_chat: bool = False
    file_receive_timeout: float = 30.0  # NEW: timeout for file downloads
    file_poll_interval: float = 1.0     # NEW: interval to check file status
    
    @classmethod
    def from_env(cls) -> 'BridgeConfig':
        """Load configuration from environment variables"""
        ws_url = os.environ.get("SIMPLEX_WS_URL", "")
        webhook_url = os.environ.get("N8N_WEBHOOK_URL", "")
        
        if not ws_url:
            raise ValueError("SIMPLEX_WS_URL environment variable is required")
        if not webhook_url:
            raise ValueError("N8N_WEBHOOK_URL environment variable is required")
        
        return cls(
            ws_url=ws_url,
            webhook_url=webhook_url,
            whisper_api_url=os.environ.get("WHISPER_API_URL", ""),
            state_file=os.environ.get("SIMPLEX_STATE_FILE", cls.state_file),
            poll_seconds=float(os.environ.get("SIMPLEX_POLL_SECONDS", "2")),
            ws_timeout=float(os.environ.get("SIMPLEX_WS_TIMEOUT", "10")),
            ws_reconnect_delay=float(os.environ.get("SIMPLEX_WS_RECONNECT_DELAY", "5")),
            debug_ws_events=os.environ.get("SIMPLEX_DEBUG_WS_EVENTS", "0") == "1",
            webhook_max_retries=int(os.environ.get("SIMPLEX_WEBHOOK_RETRIES", "3")),
            webhook_retry_backoff=float(os.environ.get("SIMPLEX_WEBHOOK_BACKOFF", "2")),
            webhook_secret=os.environ.get("WEBHOOK_SECRET", ""),
            health_check_on_start=os.environ.get("SIMPLEX_HEALTH_CHECK", "1") == "1",
            http_port=int(os.environ.get("BRIDGE_HTTP_PORT", "8080")),
            http_bind=os.environ.get("BRIDGE_HTTP_BIND", "0.0.0.0"),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            log_file=os.environ.get("LOG_FILE", cls.log_file),
            rate_limit_per_minute=int(os.environ.get("RATE_LIMIT_PER_MINUTE", "20")),
            enable_metrics=os.environ.get("ENABLE_METRICS", "1") == "1",
            enable_group_chat=os.environ.get("ENABLE_GROUP_CHAT", "0") == "1",
            file_receive_timeout=float(os.environ.get("FILE_RECEIVE_TIMEOUT", "30")),
            file_poll_interval=float(os.environ.get("FILE_POLL_INTERVAL", "1")),
        )
    
    def __post_init__(self):
        """Validate configuration"""
        if self.poll_seconds < 0.1:
            raise ValueError("poll_seconds must be >= 0.1")
        if self.ws_timeout < 1:
            raise ValueError("ws_timeout must be >= 1")


# ============================================================
# Global State
# ============================================================

config: Optional[BridgeConfig] = None
logger: Optional[logging.Logger] = None
running = True
metrics = None
rate_limiter = None
ws_connection: Optional[websocket.WebSocket] = None
state: Dict[str, int] = {}
# Track files we're currently waiting to download
pending_files: Dict[int, Dict[str, Any]] = {}


# ============================================================
# Logging Setup
# ============================================================

def setup_logging(config: BridgeConfig) -> logging.Logger:
    """Configure logging with file rotation"""
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    
    # Create logger
    logger = logging.getLogger("simplex-bridge")
    logger.setLevel(log_level)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler with rotation
    try:
        log_dir = os.path.dirname(config.log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            config.log_file,
            maxBytes=config.log_max_bytes,
            backupCount=config.log_backup_count
        )
        file_handler.setLevel(log_level)
        file_format = logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(funcName)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not setup file logging: {e}")
    
    return logger


# ============================================================
# Whisper Integration
# ============================================================

def transcribe_voice_message(file_path: str, whisper_url: str, logger) -> Optional[str]:
    """
    Transcribe a voice message using Whisper API
    
    Args:
        file_path: Path to the voice file from SimpleX
        whisper_url: URL of the Whisper transcription API
        logger: Logger instance
    
    Returns:
        Transcribed text or None if transcription fails
    """
    if not whisper_url:
        logger.debug("WHISPER_API_URL not configured, skipping transcription")
        return None
    
    if not file_path or not os.path.exists(file_path):
        logger.warning(f"Voice file not found: {file_path}")
        return None
    
    try:
        # Read the audio file
        with open(file_path, 'rb') as f:
            audio_data = f.read()
        
        # Determine content type
        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = 'audio/ogg'  # SimpleX default
        
        # Create multipart form data
        boundary = '----WebKitFormBoundary' + os.urandom(16).hex()
        body = []
        
        # Add file field
        body.append(f'--{boundary}'.encode())
        body.append(f'Content-Disposition: form-data; name="file"; filename="{os.path.basename(file_path)}"'.encode())
        body.append(f'Content-Type: {content_type}'.encode())
        body.append(b'')
        body.append(audio_data)
        
        # Add model field (required by Whisper API)
        body.append(f'--{boundary}'.encode())
        body.append(b'Content-Disposition: form-data; name="model"')
        body.append(b'')
        body.append(b'whisper-1')
        
        # Add response_format field
        body.append(f'--{boundary}'.encode())
        body.append(b'Content-Disposition: form-data; name="response_format"')
        body.append(b'')
        body.append(b'json')
        
        body.append(f'--{boundary}--'.encode())
        body.append(b'')
        
        body_bytes = b'\r\n'.join(body)
        
        # Make request to Whisper
        req = urllib.request.Request(
            whisper_url,
            data=body_bytes,
            headers={
                'Content-Type': f'multipart/form-data; boundary={boundary}',
                'Content-Length': str(len(body_bytes))
            },
            method='POST'
        )
        
        logger.info(f"🎤 Transcribing voice message: {file_path} ({len(audio_data)} bytes)")
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            transcription = result.get('text', '').strip()
            
            if transcription:
                logger.info(f"✅ Transcribed ({len(transcription)} chars): {transcription[:100]}...")
                return transcription
            else:
                logger.warning("Whisper returned empty transcription")
                return None
                
    except urllib.error.HTTPError as e:
        logger.error(f"Whisper API error {e.code}: {e.reason}")
        try:
            error_body = e.read().decode('utf-8')
            logger.error(f"Error details: {error_body}")
        except:
            pass
        return None
    except Exception as e:
        logger.error(f"Voice transcription failed: {e}")
        return None


# ============================================================
# Metrics
# ============================================================

@dataclass
class BridgeMetrics:
    """Metrics collection for monitoring"""
    start_time: float = field(default_factory=time.time)
    messages_received: int = 0
    messages_sent: int = 0
    messages_forwarded: int = 0
    webhook_failures: int = 0
    connection_errors: int = 0
    reconnections: int = 0
    rate_limited: int = 0
    state_saves: int = 0
    voice_transcriptions: int = 0
    transcription_failures: int = 0
    files_accepted: int = 0      # NEW
    files_downloaded: int = 0    # NEW
    file_timeouts: int = 0       # NEW
    last_message_time: float = 0
    message_types: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    def increment(self, metric: str, amount: int = 1):
        """Increment a metric"""
        if hasattr(self, metric):
            setattr(self, metric, getattr(self, metric) + amount)
    
    def record_message_type(self, msg_type: str):
        """Record message type for stats"""
        self.message_types[msg_type] += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        uptime = time.time() - self.start_time
        return {
            "uptime_seconds": uptime,
            "messages_received": self.messages_received,
            "messages_sent": self.messages_sent,
            "messages_forwarded": self.messages_forwarded,
            "webhook_failures": self.webhook_failures,
            "connection_errors": self.connection_errors,
            "reconnections": self.reconnections,
            "rate_limited": self.rate_limited,
            "state_saves": self.state_saves,
            "voice_transcriptions": self.voice_transcriptions,
            "transcription_failures": self.transcription_failures,
            "files_accepted": self.files_accepted,
            "files_downloaded": self.files_downloaded,
            "file_timeouts": self.file_timeouts,
            "last_message_time": self.last_message_time,
            "seconds_since_last_message": time.time() - self.last_message_time if self.last_message_time > 0 else 0,
            "messages_per_minute": (self.messages_received / uptime * 60) if uptime > 0 else 0,
            "message_types": dict(self.message_types),
        }


# ============================================================
# Rate Limiting
# ============================================================

class RateLimiter:
    """Rate limiter to prevent spam"""
    
    def __init__(self, max_per_minute: int):
        self.max_per_minute = max_per_minute
        self.contact_timestamps: Dict[str, List[datetime]] = defaultdict(list)
    
    def is_allowed(self, contact_id: str) -> bool:
        """Check if message from contact is allowed"""
        now = datetime.now()
        cutoff = now - timedelta(minutes=1)
        
        # Remove old timestamps
        self.contact_timestamps[contact_id] = [
            ts for ts in self.contact_timestamps[contact_id]
            if ts > cutoff
        ]
        
        # Check limit
        if len(self.contact_timestamps[contact_id]) >= self.max_per_minute:
            return False
        
        # Record this message
        self.contact_timestamps[contact_id].append(now)
        return True
    
    def get_stats(self) -> Dict[str, int]:
        """Get rate limiter stats"""
        return {
            "tracked_contacts": len(self.contact_timestamps),
            "total_recent_messages": sum(len(timestamps) for timestamps in self.contact_timestamps.values())
        }


# ============================================================
# State Management
# ============================================================

def ensure_state_dir():
    """Create state directory if it doesn't exist"""
    state_dir = os.path.dirname(config.state_file)
    if state_dir:
        os.makedirs(state_dir, exist_ok=True)


def load_state() -> Dict[str, int]:
    """Load deduplication state from file"""
    try:
        with open(config.state_file, "r") as f:
            raw = f.read().strip()
            if not raw:
                return {}
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("State must be a dict")
            return {str(k): int(v) for k, v in data.items()}
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning(f"State file corrupted ({type(e).__name__}: {e}), starting fresh")
        return {}
    except Exception as e:
        logger.warning(f"State load error: {repr(e)}, starting fresh")
        return {}


def save_state(state: Dict[str, int]):
    """Atomically save state to file"""
    tmp = config.state_file + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, config.state_file)
        metrics.increment("state_saves")
    except Exception as e:
        logger.error(f"Failed to save state: {repr(e)}")
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def cleanup_old_state(state: Dict[str, int], max_contacts: int = 1000) -> Dict[str, int]:
    """Remove excess old contacts from state"""
    if len(state) <= max_contacts:
        return state
    
    logger.info(f"Cleaning up state: {len(state)} contacts, keeping {max_contacts}")
    
    # Sort by itemId (oldest first) and keep most recent
    sorted_contacts = sorted(state.items(), key=lambda x: x[1])
    cleaned = dict(sorted_contacts[-max_contacts:])
    
    logger.info(f"State cleaned: {len(state) - len(cleaned)} old contacts removed")
    return cleaned


# ============================================================
# WebSocket Management
# ============================================================

def create_websocket_connection() -> websocket.WebSocket:
    """Create new WebSocket connection"""
    logger.info(f"Connecting to SimpleX at {config.ws_url}...")
    ws = websocket.create_connection(config.ws_url, timeout=config.ws_timeout)
    ws.settimeout(config.ws_timeout)
    logger.info("✅ Connected to SimpleX!")
    return ws


def get_or_reconnect_websocket() -> Optional[websocket.WebSocket]:
    """Get existing WebSocket or create new one"""
    global ws_connection
    
    if ws_connection is not None:
        try:
            # Test if connection is alive
            ws_connection.ping()
            return ws_connection
        except Exception as e:
            logger.warning(f"WebSocket connection lost: {e}")
            try:
                ws_connection.close()
            except:
                pass
            ws_connection = None
    
    # Need to reconnect
    try:
        ws_connection = create_websocket_connection()
        metrics.increment("reconnections")
        return ws_connection
    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        metrics.increment("connection_errors")
        return None


def ws_cmd(ws: websocket.WebSocket, corr_id: str, command: str, timeout: Optional[float] = None) -> Dict[str, Any]:
    """Send command and wait for matching corrId response"""
    if timeout is None:
        timeout = config.ws_timeout
    
    try:
        ws.send(json.dumps({"corrId": corr_id, "cmd": command}))
    except websocket.WebSocketConnectionClosedException:
        raise ConnectionError("WebSocket closed before send")
    except Exception as e:
        raise ConnectionError(f"WebSocket send failed: {repr(e)}")
    
    end = time.time() + timeout
    
    while time.time() < end:
        remaining = end - time.time()
        if remaining <= 0:
            break
        
        try:
            ws.settimeout(remaining)
            msg = ws.recv()
        except websocket.WebSocketTimeoutException:
            break
        except websocket.WebSocketConnectionClosedException:
            raise ConnectionError("WebSocket closed while waiting for response")
        except Exception as e:
            raise ConnectionError(f"WebSocket recv failed: {repr(e)}")
        
        try:
            j = json.loads(msg)
        except json.JSONDecodeError:
            continue
        
        if j.get("corrId") == corr_id:
            return j
        
        # Log async events if debugging enabled
        if config.debug_ws_events:
            r = j.get("resp") or {}
            if isinstance(r, dict) and "type" in r:
                logger.debug(f"WS async event: {r.get('type')}")
    
    raise TimeoutError(f"No response for corrId={corr_id} cmd={command!r} within {timeout}s")


# ============================================================
# File Reception (NEW)
# ============================================================

def accept_file(ws: websocket.WebSocket, file_id: int) -> bool:
    """
    Accept a file transfer by sending /fr command
    
    Args:
        ws: WebSocket connection
        file_id: SimpleX file ID to accept
    
    Returns:
        True if accept command was sent successfully
    """
    try:
        corr_id = f"fr-{file_id}-{int(time.time() * 1000)}"
        cmd = f"/fr {file_id}"
        
        logger.info(f"📥 Accepting file {file_id}...")
        resp = ws_cmd(ws, corr_id, cmd, timeout=config.ws_timeout)
        
        # Check response for errors
        resp_data = resp.get("resp", {})
        if resp_data.get("type") == "chatCmdError":
            error = resp_data.get("chatError", {})
            logger.error(f"Failed to accept file {file_id}: {error}")
            return False
        
        logger.info(f"✅ File {file_id} acceptance initiated")
        metrics.increment("files_accepted")
        return True
        
    except Exception as e:
        logger.error(f"Error accepting file {file_id}: {e}")
        return False


def get_file_status(ws: websocket.WebSocket, file_id: int) -> Optional[Dict[str, Any]]:
    """
    Get current status of a file transfer
    
    Args:
        ws: WebSocket connection
        file_id: SimpleX file ID
    
    Returns:
        File status dict or None if not found
    """
    try:
        corr_id = f"fs-{file_id}-{int(time.time() * 1000)}"
        cmd = f"/fstatus {file_id}"
        
        resp = ws_cmd(ws, corr_id, cmd, timeout=config.ws_timeout)
        return resp.get("resp", {})
        
    except Exception as e:
        logger.debug(f"Error getting file status {file_id}: {e}")
        return None


def wait_for_file_download(ws: websocket.WebSocket, file_id: int, file_name: str) -> Optional[str]:
    """
    Wait for a file to finish downloading
    
    Args:
        ws: WebSocket connection
        file_id: SimpleX file ID
        file_name: Expected filename
    
    Returns:
        File path if download completed, None otherwise
    """
    start_time = time.time()
    
    while time.time() - start_time < config.file_receive_timeout:
        # Check /tmp first (default SimpleX download location)
        possible_paths = [
            f"/tmp/{file_name}",
            f"/home/simplex/.simplex/files/{file_name}",
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                # Verify file is complete (size > 0 and not growing)
                size1 = os.path.getsize(path)
                time.sleep(0.2)
                size2 = os.path.getsize(path)
                
                if size1 > 0 and size1 == size2:
                    logger.info(f"✅ File downloaded: {path} ({size1} bytes)")
                    metrics.increment("files_downloaded")
                    return path
        
        time.sleep(config.file_poll_interval)
    
    logger.warning(f"⏱️ Timeout waiting for file {file_id} ({file_name})")
    metrics.increment("file_timeouts")
    return None


# ============================================================
# Message Extraction & Normalization (UPDATED)
# ============================================================

def extract_direct_message(ci: Dict[str, Any], ws: websocket.WebSocket = None) -> Optional[Dict[str, Any]]:
    """
    Extract direct message with proper file handling
    
    FIXED: Now correctly reads file info from chatItem.file instead of msgContent.voice
    """
    chatInfo = ci.get("chatInfo") or {}
    contact = chatInfo.get("contact") or {}
    contact_id = contact.get("contactId")
    display_name = (contact.get("localDisplayName") or "").strip()
    
    chatItem = ci.get("chatItem") or {}
    chat_dir = chatItem.get("chatDir") or {}
    chat_dir_type = (chat_dir.get("type") or "").strip()
    
    meta = chatItem.get("meta") or {}
    item_id = meta.get("itemId")
    item_ts = meta.get("itemTs")
    created_at = meta.get("createdAt")
    
    content = chatItem.get("content") or {}
    msg_content = content.get("msgContent") or {}
    
    # FIXED: Get file info from chatItem level, not inside msgContent
    file_info = chatItem.get("file") or {}
    
    # Only process received messages
    if chat_dir_type != "directRcv":
        return None
    
    # Must have essential fields
    if contact_id is None or item_id is None:
        return None
    
    # Detect message type
    msg_type = msg_content.get("type", "text")
    text = msg_content.get("text", "")
    
    base_msg = {
        "contactId": int(contact_id),
        "displayName": display_name,
        "itemId": int(item_id),
        "itemTs": item_ts,
        "createdAt": created_at,
        "chatDir": chat_dir_type,
        "chatType": "direct",
        "raw": ci,
    }
    
    # Handle different message types
    if msg_type == "voice":
        # FIXED: Get file details from chatItem.file
        file_id = file_info.get("fileId")
        file_name = file_info.get("fileName")
        file_size = file_info.get("fileSize")
        file_status = file_info.get("fileStatus", {})
        file_status_type = file_status.get("type", "")
        file_path = file_status.get("filePath")  # Only present when downloaded
        
        duration = msg_content.get("duration", 0)
        
        logger.debug(f"Voice message: fileId={file_id}, fileName={file_name}, "
                    f"status={file_status_type}, filePath={file_path}")
        
        # If file needs to be accepted and we have a WebSocket connection
        if file_status_type == "rcvInvitation" and file_id and ws:
            logger.info(f"🎤 Voice message needs file acceptance (fileId={file_id})")
            
            # Accept the file
            if accept_file(ws, file_id):
                # Wait for download to complete
                file_path = wait_for_file_download(ws, file_id, file_name)
        
        # Try to transcribe if we have a file path
        transcription = None
        if file_path and config.whisper_api_url:
            logger.info(f"🎤 Attempting to transcribe: {file_path}")
            transcription = transcribe_voice_message(file_path, config.whisper_api_url, logger)
            if transcription:
                metrics.increment("voice_transcriptions")
            else:
                metrics.increment("transcription_failures")
        elif not file_path:
            logger.warning(f"Cannot transcribe: file not downloaded (status={file_status_type})")
        elif not config.whisper_api_url:
            logger.debug("Whisper not configured, skipping transcription")
        
        return {
            **base_msg,
            "type": "voice",
            "text": transcription or text or "[Voice message - transcription unavailable]",
            "filePath": file_path,
            "fileId": file_id,
            "fileName": file_name,
            "fileSize": file_size,
            "duration": duration,
            "transcribed": bool(transcription),
        }
    
    elif msg_type == "image":
        file_path = file_info.get("fileStatus", {}).get("filePath")
        return {
            **base_msg,
            "type": "image",
            "text": text or "[Image]",
            "filePath": file_path,
            "fileId": file_info.get("fileId"),
            "fileName": file_info.get("fileName"),
        }
    
    elif msg_type == "file":
        file_path = file_info.get("fileStatus", {}).get("filePath")
        return {
            **base_msg,
            "type": "file",
            "text": text or f"[File: {file_info.get('fileName', 'unknown')}]",
            "filePath": file_path,
            "fileId": file_info.get("fileId"),
            "fileName": file_info.get("fileName"),
            "fileSize": file_info.get("fileSize"),
        }
    
    else:
        # Text message
        if not text:
            return None
        return {
            **base_msg,
            "type": "text",
            "text": str(text),
        }


def extract_group_message(ci: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract group message (if enabled)"""
    if not config.enable_group_chat:
        return None
    
    chatInfo = ci.get("chatInfo") or {}
    group_info = chatInfo.get("groupInfo") or {}
    member = chatInfo.get("groupMember") or {}
    
    group_id = group_info.get("groupId")
    group_name = group_info.get("displayName", "")
    member_id = member.get("groupMemberId")
    member_name = member.get("displayName", "")
    
    chatItem = ci.get("chatItem") or {}
    chat_dir = chatItem.get("chatDir") or {}
    chat_dir_type = (chat_dir.get("type") or "").strip()
    
    meta = chatItem.get("meta") or {}
    item_id = meta.get("itemId")
    item_ts = meta.get("itemTs")
    created_at = meta.get("createdAt")
    
    content = chatItem.get("content") or {}
    msg_content = content.get("msgContent") or {}
    
    # Only process received group messages
    if chat_dir_type != "groupRcv":
        return None
    
    if group_id is None or item_id is None:
        return None
    
    msg_type = msg_content.get("type", "text")
    text = msg_content.get("text", "")
    
    if not text and msg_type == "text":
        return None
    
    return {
        "groupId": int(group_id),
        "groupName": group_name,
        "memberId": member_id,
        "displayName": member_name,
        "type": msg_type,
        "text": str(text),
        "itemId": int(item_id),
        "itemTs": item_ts,
        "createdAt": created_at,
        "chatDir": chat_dir_type,
        "chatType": "group",
        "raw": ci,
    }


def extract_message(ci: Dict[str, Any], ws: websocket.WebSocket = None) -> Optional[Dict[str, Any]]:
    """Extract and normalize a message from chat item"""
    chatInfo = ci.get("chatInfo") or {}
    chat_type = chatInfo.get("type")
    
    if chat_type == "direct":
        return extract_direct_message(ci, ws)
    elif chat_type == "group":
        return extract_group_message(ci)
    else:
        return None


# ============================================================
# Webhook Communication
# ============================================================

def sign_payload(payload: bytes) -> str:
    """Generate HMAC signature for payload"""
    if not config.webhook_secret:
        return ""
    return hmac.new(
        config.webhook_secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()


def post_to_webhook(payload: Dict[str, Any]) -> str:
    """POST JSON payload to webhook"""
    data = json.dumps(payload).encode("utf-8")
    
    headers = {"Content-Type": "application/json"}
    
    # Add HMAC signature if secret configured
    if config.webhook_secret:
        headers["X-Signature"] = sign_payload(data)
    
    req = urllib.request.Request(
        config.webhook_url,
        data=data,
        headers=headers,
        method="POST",
    )
    
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read().decode("utf-8", "ignore")


def post_with_retry(payload: Dict[str, Any]) -> str:
    """POST with exponential backoff retry"""
    last_error = None
    
    for attempt in range(config.webhook_max_retries):
        try:
            return post_to_webhook(payload)
        except urllib.error.HTTPError as e:
            # Don't retry client errors (4xx) except 429 (rate limit)
            if 400 <= e.code < 500 and e.code != 429:
                logger.error(f"Webhook returned {e.code}, not retrying")
                metrics.increment("webhook_failures")
                raise
            last_error = e
        except Exception as e:
            last_error = e
        
        if attempt < config.webhook_max_retries - 1:
            wait_time = config.webhook_retry_backoff * (2 ** attempt)
            logger.warning(f"Webhook POST failed (attempt {attempt + 1}/{config.webhook_max_retries}): {repr(last_error)}")
            logger.warning(f"Retrying in {wait_time:.1f}s...")
            time.sleep(wait_time)
    
    logger.error(f"Webhook POST failed after {config.webhook_max_retries} attempts")
    metrics.increment("webhook_failures")
    raise last_error


# ============================================================
# Message Processing
# ============================================================

def build_webhook_payload(msg: Dict[str, Any]) -> Dict[str, Any]:
    """Build webhook payload from message"""
    payload = {
        "source": "simplex",
        "chatType": msg.get("chatType", "direct"),
        "type": msg.get("type", "text"),
        "text": msg["text"],
        "itemId": msg["itemId"],
        "itemTs": msg.get("itemTs"),
        "createdAt": msg.get("createdAt"),
        "raw_item": msg["raw"],
        "ts": time.time(),
    }
    
    if msg["chatType"] == "direct":
        payload["contactId"] = msg["contactId"]
        payload["displayName"] = msg["displayName"]
        payload["chatDir"] = {"type": msg["chatDir"]}
    elif msg["chatType"] == "group":
        payload["groupId"] = msg["groupId"]
        payload["groupName"] = msg["groupName"]
        payload["memberId"] = msg.get("memberId")
        payload["displayName"] = msg["displayName"]
    
    # Add type-specific fields
    if msg.get("type") == "voice":
        payload["voice"] = {
            "filePath": msg.get("filePath"),
            "fileId": msg.get("fileId"),
            "fileName": msg.get("fileName"),
            "fileSize": msg.get("fileSize"),
            "duration": msg.get("duration"),
            "transcribed": msg.get("transcribed", False),
        }
    elif msg.get("type") == "image":
        payload["image"] = {
            "filePath": msg.get("filePath"),
            "fileId": msg.get("fileId"),
            "fileName": msg.get("fileName"),
        }
    elif msg.get("type") == "file":
        payload["file"] = {
            "filePath": msg.get("filePath"),
            "fileId": msg.get("fileId"),
            "fileName": msg.get("fileName"),
            "fileSize": msg.get("fileSize"),
        }
    
    return payload


def process_single_message(msg: Dict[str, Any], state: Dict[str, int]) -> bool:
    """Process and forward a single message"""
    # Generate state key (contactId or groupId)
    if msg["chatType"] == "direct":
        state_key = str(msg["contactId"])
    elif msg["chatType"] == "group":
        state_key = f"group_{msg['groupId']}"
    else:
        return False
    
    last_seen = int(state.get(state_key, 0))
    
    # Skip already-processed messages
    if msg["itemId"] <= last_seen:
        return False
    
    # Rate limiting (only for direct messages)
    if msg["chatType"] == "direct":
        if not rate_limiter.is_allowed(state_key):
            logger.warning(f"Rate limit exceeded for contact {msg['contactId']}")
            metrics.increment("rate_limited")
            return False
    
    # Build and send payload
    payload = build_webhook_payload(msg)
    
    try:
        result = post_with_retry(payload)
        logger.info(
            f"✅ Posted: {msg['chatType']} type={msg['type']} "
            f"itemId={msg['itemId']} from=\"{msg['displayName']}\" "
            f"text={msg['text'][:50]!r}"
        )
        
        # Update state only after successful webhook
        state[state_key] = msg["itemId"]
        save_state(state)
        
        metrics.increment("messages_forwarded")
        metrics.record_message_type(msg["type"])
        metrics.last_message_time = time.time()
        
        return True
    except Exception as e:
        logger.error(f"❌ Could not post message: {repr(e)}")
        return False


def fetch_and_process_messages(ws: websocket.WebSocket, state: Dict[str, int]) -> int:
    """Fetch new messages and process them"""
    try:
        resp = ws_cmd(ws, "tail", "/tail", timeout=config.ws_timeout)
    except Exception as e:
        logger.error(f"Failed to fetch messages: {e}")
        metrics.increment("connection_errors")
        raise
    
    chat_items = (resp.get("resp") or {}).get("chatItems") or []
    
    if not chat_items:
        logger.debug("No chat items in /tail response")
        return 0
    
    # Extract messages (pass ws for file acceptance)
    messages = []
    for ci in chat_items:
        msg = extract_message(ci, ws)  # UPDATED: pass ws connection
        if msg:
            messages.append(msg)
            metrics.increment("messages_received")
    
    if not messages:
        logger.debug("No processable messages found")
        return 0
    
    # Sort oldest → newest
    messages.sort(key=lambda m: m["itemId"])
    
    # Process messages
    forwarded = 0
    for msg in messages:
        if not running:
            break
        if process_single_message(msg, state):
            forwarded += 1
    
    if forwarded == 0 and messages:
        logger.debug(f"All {len(messages)} messages already processed")
    
    return forwarded


# ============================================================
# Sending Messages to SimpleX
# ============================================================

def send_to_simplex(contact_id: int, text: str) -> bool:
    """Send a message to a SimpleX contact"""
    try:
        ws = get_or_reconnect_websocket()
        if not ws:
            raise ConnectionError("No WebSocket connection")
        
        # SimpleX send message command format
        cmd = f"@{contact_id} {text}"
        corr_id = f"send-{contact_id}-{int(time.time() * 1000)}"
        
        resp = ws_cmd(ws, corr_id, cmd, timeout=config.ws_timeout)
        
        logger.info(f"✅ Sent message to contact {contact_id}: {text[:50]!r}")
        metrics.increment("messages_sent")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send message to contact {contact_id}: {e}")
        return False


# ============================================================
# HTTP Server for Control Endpoints
# ============================================================

class BridgeHTTPHandler(BaseHTTPRequestHandler):
    """HTTP handler for health, metrics, and message sending"""
    
    def log_message(self, format, *args):
        """Suppress default request logging"""
        pass
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == "/health":
            self.handle_health()
        elif self.path == "/metrics":
            self.handle_metrics()
        elif self.path == "/state":
            self.handle_state()
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "Not found"}')
    
    def do_POST(self):
        """Handle POST requests"""
        if self.path == "/send":
            self.handle_send()
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "Not found"}')
    
    def handle_health(self):
        """Health check endpoint"""
        health_status = {
            "status": "healthy" if running else "stopped",
            "ws_connected": ws_connection is not None,
            "state_contacts": len(state),
            "whisper_configured": bool(config.whisper_api_url),
            "version": "2.1",  # UPDATED version
        }
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(health_status).encode())
    
    def handle_metrics(self):
        """Metrics endpoint"""
        if not config.enable_metrics:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b'{"error": "Metrics disabled"}')
            return
        
        metrics_data = metrics.to_dict()
        metrics_data["rate_limiter"] = rate_limiter.get_stats()
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(metrics_data, indent=2).encode())
    
    def handle_state(self):
        """State inspection endpoint"""
        state_info = {
            "contacts": len(state),
            "recent": [
                {"key": k, "itemId": v}
                for k, v in sorted(state.items(), key=lambda x: x[1], reverse=True)[:10]
            ]
        }
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(state_info, indent=2).encode())
    
    def handle_send(self):
        """Send message endpoint"""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error": "No body"}')
                return
            
            body = json.loads(self.rfile.read(content_length))
            
            contact_id = body.get("contactId")
            text = body.get("text")
            
            if not contact_id or not text:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error": "Missing contactId or text"}')
                return
            
            success = send_to_simplex(int(contact_id), text)
            
            if success:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "sent"}).encode())
            else:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Failed to send"}).encode())
        
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error": "Invalid JSON"}')
        except Exception as e:
            logger.error(f"Error in /send endpoint: {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())


def start_http_server():
    """Start HTTP server in background thread"""
    try:
        server = HTTPServer((config.http_bind, config.http_port), BridgeHTTPHandler)
        logger.info(f"✅ HTTP server listening on {config.http_bind}:{config.http_port}")
        logger.info(f"------------------------------------------------------------")
        logger.info(f"   - GET  /health  - Health check")
        logger.info(f"   - GET  /metrics - Metrics")
        logger.info(f"   - GET  /state   - State info")
        logger.info(f"   - POST /send    - Send message to SimpleX")
        server.serve_forever()
    except Exception as e:
        logger.error(f"HTTP server failed: {e}")


# ============================================================
# Health Checks
# ============================================================

def check_simplex_api() -> tuple[bool, str]:
    """Verify SimpleX WebSocket API is reachable"""
    try:
        ws = websocket.create_connection(config.ws_url, timeout=5)
        ws.settimeout(5)
        ws_cmd(ws, "health-check", "/help", timeout=5)
        ws.close()
        return True, "OK"
    except Exception as e:
        return False, str(e)


def check_n8n_reachable() -> tuple[bool, str]:
    """Verify n8n is reachable"""
    try:
        parsed = urlparse(config.webhook_url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        sock = socket.create_connection((host, port), timeout=5)
        sock.close()
        return True, "OK"
    except Exception as e:
        return False, str(e)


def check_whisper_reachable() -> tuple[bool, str]:
    """Verify Whisper is reachable"""
    if not config.whisper_api_url:
        return True, "Not configured (optional)"
    
    try:
        parsed = urlparse(config.whisper_api_url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        sock = socket.create_connection((host, port), timeout=5)
        sock.close()
        return True, "OK"
    except Exception as e:
        return False, str(e)


def run_health_checks():
    """Run startup health checks"""
    logger.info("============================================================")
    logger.info("Running startup health checks...")
    logger.info("============================================================")
    
    all_ok = True
    
    simplex_ok, simplex_msg = check_simplex_api()
    status = "✓" if simplex_ok else "✗"
    logger.info(f"  {status} SimpleX API ({config.ws_url}): {simplex_msg}")
    if not simplex_ok:
        all_ok = False
    
    n8n_ok, n8n_msg = check_n8n_reachable()
    status = "✓" if n8n_ok else "✗"
    logger.info(f"  {status} n8n ({config.webhook_url}): {n8n_msg}")
    if not n8n_ok:
        all_ok = False
    
    whisper_ok, whisper_msg = check_whisper_reachable()
    status = "✓" if whisper_ok else "✗"
    logger.info(f"  {status} Whisper ({config.whisper_api_url or 'not configured'}): {whisper_msg}")
    if not whisper_ok and config.whisper_api_url:
        logger.warning("    Voice transcription will not work!")
    
    logger.info("============================================================")
    
    if all_ok:
        logger.info("✅ All health checks passed!")
    else:
        logger.warning("⚠️  Some health checks failed!")
        logger.warning("The bridge will still start, but may not work correctly.")
    
    logger.info("============================================================")


# ============================================================
# Graceful Shutdown
# ============================================================

def shutdown_handler(signum, frame):
    """Handle SIGTERM/SIGINT for clean shutdown"""
    global running
    sig_name = signal.Signals(signum).name
    logger.info(f"\n[{sig_name}] Shutdown signal received, exiting gracefully...")
    running = False


# ============================================================
# Main Loop
# ============================================================

def main():
    global config, logger, running, metrics, rate_limiter, state, ws_connection
    
    # Load configuration
    try:
        config = BridgeConfig.from_env()
    except Exception as e:
        print(f"ERROR: Configuration error: {e}")
        return 1
    
    # Setup logging
    logger = setup_logging(config)
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)
    
    # Print banner
    logger.info("")
    logger.info("╔════════════════════════════════════════════════════════════╗")
    logger.info("║   SimpleX ↔ n8n Bridge v2.1 with Voice Auto-Accept       ║")
    logger.info("╚════════════════════════════════════════════════════════════╝")
    logger.info("")
    logger.info("Configuration:")
    logger.info(f"  SIMPLEX_WS_URL:      {config.ws_url}")
    logger.info(f"  N8N_WEBHOOK_URL:     {config.webhook_url}")
    logger.info(f"  WHISPER_API_URL:     {config.whisper_api_url or '(not configured)'}")
    logger.info(f"  STATE_FILE:          {config.state_file}")
    logger.info(f"  POLL_SECONDS:        {config.poll_seconds}")
    logger.info(f"  HTTP_PORT:           {config.http_port}")
    logger.info(f"  LOG_LEVEL:           {config.log_level}")
    logger.info(f"  RATE_LIMIT:          {config.rate_limit_per_minute}/min")
    logger.info(f"  FILE_TIMEOUT:        {config.file_receive_timeout}s")
    logger.info(f"  WEBHOOK_AUTH:        {'Enabled' if config.webhook_secret else 'Disabled'}")
    logger.info(f"  GROUP_CHAT:          {'Enabled' if config.enable_group_chat else 'Disabled'}")
    logger.info(f"  VOICE_TRANSCRIPTION: {'Enabled' if config.whisper_api_url else 'Disabled'}")
    logger.info("")
    
    # Initialize globals
    metrics = BridgeMetrics()
    rate_limiter = RateLimiter(config.rate_limit_per_minute)
    
    # Run health checks
    if config.health_check_on_start:
        run_health_checks()
        logger.info("")
    
    # Setup state
    ensure_state_dir()
    state = load_state()
    
    if state:
        logger.info(f"Loaded state for {len(state)} contact(s)")
    else:
        logger.info("No previous state found, starting fresh")
    logger.info("")
    
    # Start HTTP server
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    logger.info("")
    
    logger.info("Entering main loop (Ctrl+C to stop)...")
    logger.info("-" * 60)
    
    consecutive_errors = 0
    max_consecutive_errors = 10
    last_cleanup = time.time()
    cleanup_interval = 3600  # 1 hour
    
    while running:
        try:
            # Get or reconnect WebSocket
            ws = get_or_reconnect_websocket()
            
            if ws is None:
                logger.error("No WebSocket connection, waiting before retry...")
                time.sleep(config.ws_reconnect_delay)
                continue
            
            # Fetch and process messages
            forwarded = fetch_and_process_messages(ws, state)
            
            # Reset error counter on success
            consecutive_errors = 0
            
            # Periodic state cleanup
            if time.time() - last_cleanup > cleanup_interval:
                if len(state) > config.state_cleanup_max_contacts:
                    state = cleanup_old_state(state, config.state_cleanup_max_contacts)
                    save_state(state)
                last_cleanup = time.time()
            
            # Wait before next poll
            if running:
                time.sleep(config.poll_seconds)
        
        except (ConnectionError, TimeoutError) as e:
            consecutive_errors += 1
            logger.error(f"Connection issue ({consecutive_errors}/{max_consecutive_errors}): {repr(e)}")
            
            # Force reconnect
            if ws_connection:
                try:
                    ws_connection.close()
                except:
                    pass
                ws_connection = None
            
            if consecutive_errors >= max_consecutive_errors:
                logger.warning("Too many consecutive errors, waiting longer...")
                time.sleep(config.poll_seconds * 5)
                consecutive_errors = 0
            else:
                time.sleep(config.ws_reconnect_delay)
        
        except Exception as e:
            consecutive_errors += 1
            logger.error(f"Bridge error ({consecutive_errors}/{max_consecutive_errors}): {repr(e)}", exc_info=True)
            
            if consecutive_errors >= max_consecutive_errors:
                logger.warning("Too many consecutive errors, waiting longer...")
                time.sleep(config.poll_seconds * 5)
                consecutive_errors = 0
    
    # Cleanup
    logger.info("")
    logger.info("-" * 60)
    logger.info("Bridge stopped cleanly. Final stats:")
    logger.info(json.dumps(metrics.to_dict(), indent=2))
    logger.info("Goodbye! 👋")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
