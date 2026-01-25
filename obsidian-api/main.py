"""
Obsidian Vault API v2.6.0 - Database-oriented Second Brain
Supports: People, Projects, Ideas, Admin, Inbox Log

New in 2.6.0:
- POST /pending_delete/multi - Store multiple matches for selection
- POST /pending_delete/select/{number} - Select match by number (1-indexed)
- GET /pending_delete now returns matches array for multi-match scenarios
- Backwards compatible with single-match pending delete

Previous versions:
- 2.5.1: pending_delete endpoints for confirmation flow
- 2.5.0: POST /fix, GET /pending for "Needs Review" entries
- 2.3.x: Generic database endpoints, tags, recent, etc.
"""

from fastapi import FastAPI, HTTPException, Query, Body
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime, date
from pathlib import Path
from enum import Enum
import os
import re
import yaml
import json
import uuid

app = FastAPI(
    title="Obsidian Vault API",
    description="Database-oriented REST API for Obsidian second brain",
    version="2.6.0"
)

# Configuration
VAULT_PATH = Path(os.getenv("VAULT_PATH", "/vault"))

# Database folders
DATABASES = {
    "people": VAULT_PATH / "People",
    "projects": VAULT_PATH / "Projects", 
    "ideas": VAULT_PATH / "Ideas",
    "admin": VAULT_PATH / "Admin",
    "inbox_log": VAULT_PATH / "Inbox Log",
    "daily": VAULT_PATH / "Daily Notes"
}

# Content databases (excludes logs and daily notes)
CONTENT_DATABASES = ["people", "projects", "ideas", "admin"]

# Ensure all database folders exist
for db_path in DATABASES.values():
    db_path.mkdir(parents=True, exist_ok=True)


# ============== Enums ==============

class ProjectStatus(str, Enum):
    ACTIVE = "Active"
    WAITING = "Waiting"
    BLOCKED = "Blocked"
    SOMEDAY = "Someday"
    DONE = "Done"

class AdminStatus(str, Enum):
    TODO = "Todo"
    DONE = "Done"

class InboxStatus(str, Enum):
    FILED = "Filed"
    NEEDS_REVIEW = "Needs Review"
    FIXED = "Fixed"

class FiledTo(str, Enum):
    PEOPLE = "People"
    PROJECTS = "Projects"
    IDEAS = "Ideas"
    ADMIN = "Admin"
    NEEDS_REVIEW = "Needs Review"


# ============== Database Models ==============

class PersonCreate(BaseModel):
    """People Database record"""
    name: str = Field(..., description="Person's name")
    context: Optional[str] = Field(None, description="How you know them, their role, relationship")
    follow_ups: Optional[str] = Field(None, description="Things to remember for next conversation")
    tags: Optional[List[str]] = Field(default_factory=list, description="family, work, friend, etc.")

class PersonUpdate(BaseModel):
    context: Optional[str] = None
    follow_ups: Optional[str] = None
    tags: Optional[List[str]] = None
    append_follow_ups: Optional[str] = Field(None, description="Add to existing follow-ups")

class ProjectCreate(BaseModel):
    """Projects Database record"""
    name: str = Field(..., description="Project name")
    status: ProjectStatus = Field(default=ProjectStatus.ACTIVE)
    next_action: Optional[str] = Field(None, description="The literal next thing to do")
    notes: Optional[str] = Field(None, description="Context, links, details")
    tags: Optional[List[str]] = Field(default_factory=list)

class ProjectUpdate(BaseModel):
    status: Optional[ProjectStatus] = None
    next_action: Optional[str] = None
    notes: Optional[str] = None
    append_notes: Optional[str] = None
    tags: Optional[List[str]] = None

class IdeaCreate(BaseModel):
    """Ideas Database record"""
    name: str = Field(..., description="Idea title")
    one_liner: str = Field(..., description="Core insight in one sentence")
    notes: Optional[str] = Field(None, description="Elaboration, related thoughts")
    tags: Optional[List[str]] = Field(default_factory=list)

class IdeaUpdate(BaseModel):
    one_liner: Optional[str] = None
    notes: Optional[str] = None
    append_notes: Optional[str] = None
    tags: Optional[List[str]] = None

class AdminCreate(BaseModel):
    """Admin Database record (tasks)"""
    name: str = Field(..., description="Task name")
    due_date: Optional[str] = Field(None, description="YYYY-MM-DD format")
    status: AdminStatus = Field(default=AdminStatus.TODO)
    notes: Optional[str] = Field(None, description="Additional context")

class AdminUpdate(BaseModel):
    due_date: Optional[str] = None
    status: Optional[AdminStatus] = None
    notes: Optional[str] = None

class InboxLogCreate(BaseModel):
    """Inbox Log record - audit trail for all captures"""
    original_text: str = Field(..., description="Exactly what was typed in SimpleX")
    filed_to: FiledTo = Field(..., description="Which database it was filed to")
    destination_name: str = Field(..., description="Name of the created record")
    destination_url: Optional[str] = Field(None, description="Obsidian URI link")
    confidence: float = Field(..., ge=0, le=1, description="AI confidence score")
    status: InboxStatus = Field(default=InboxStatus.FILED)
    simplex_thread_ts: Optional[str] = Field(None, description="SimpleX thread timestamp")
    obsidian_record_id: Optional[str] = Field(None, description="ID for updates")


# ============== Pending Delete Models ==============

class PendingDeleteMatch(BaseModel):
    """Single match in a pending delete"""
    id: str
    database: str
    name: str

class PendingDeleteMultiRequest(BaseModel):
    """Request to store multiple matches for selection"""
    matches: List[PendingDeleteMatch]
    sender: Optional[str] = None
    query: Optional[str] = None


# ============== AI Classification Input ==============

class CaptureInput(BaseModel):
    """Raw capture from SimpleX - to be classified by AI"""
    text: str = Field(..., description="The raw message from SimpleX")
    source: str = Field(default="simplex")
    simplex_thread_ts: Optional[str] = None

class ClassifiedCapture(BaseModel):
    """AI-classified capture ready for routing"""
    original_text: str
    database: Literal["people", "projects", "ideas", "admin", "needs_review"]
    confidence: float = Field(ge=0, le=1)
    
    # Extracted fields based on database type
    name: str
    
    # People fields
    context: Optional[str] = None
    follow_ups: Optional[str] = None
    
    # Projects fields
    status: Optional[str] = None
    next_action: Optional[str] = None
    
    # Ideas fields
    one_liner: Optional[str] = None
    
    # Admin fields
    due_date: Optional[str] = None
    
    # Common
    notes: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)
    
    # Metadata
    source: str = "simplex"
    simplex_thread_ts: Optional[str] = None


# ============== Response Models ==============

class RecordResponse(BaseModel):
    id: str
    path: str
    name: str
    database: str
    frontmatter: dict
    content: str
    created: str
    modified: str
    obsidian_url: str

class DeleteResponse(BaseModel):
    success: bool
    deleted_id: str
    deleted_name: str
    database: str


# ============== Helper Functions ==============

def sanitize_filename(name: str) -> str:
    """Remove invalid characters from filename"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '-')
    return name.strip()[:100]

def generate_id() -> str:
    """Generate a short unique ID"""
    return datetime.now().strftime("%Y%m%d%H%M%S") + "-" + str(uuid.uuid4())[:8]

def get_obsidian_url(path: Path) -> str:
    """Generate obsidian:// URL for a note"""
    relative_path = path.relative_to(VAULT_PATH)
    vault_name = VAULT_PATH.name
    return f"obsidian://open?vault={vault_name}&file={relative_path}"

def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter from markdown content"""
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
                body = parts[2].lstrip('\n')
                return frontmatter, body
            except yaml.YAMLError:
                pass
    return {}, content

def create_note(database: str, name: str, frontmatter: dict, content: str = "") -> RecordResponse:
    """Create a note in a database folder"""
    db_path = DATABASES.get(database)
    if not db_path:
        raise HTTPException(status_code=400, detail=f"Unknown database: {database}")
    
    record_id = generate_id()
    filename = sanitize_filename(name) + ".md"
    filepath = db_path / filename
    
    counter = 1
    while filepath.exists():
        filename = f"{sanitize_filename(name)} ({counter}).md"
        filepath = db_path / filename
        counter += 1
    
    now = datetime.now().isoformat()
    frontmatter["id"] = record_id
    frontmatter["created"] = now
    frontmatter["last_touched"] = now
    
    fm_yaml = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
    file_content = f"---\n{fm_yaml}---\n\n{content}"
    
    filepath.write_text(file_content, encoding='utf-8')
    
    return RecordResponse(
        id=record_id,
        path=str(filepath.relative_to(VAULT_PATH)),
        name=name,
        database=database,
        frontmatter=frontmatter,
        content=content,
        created=now,
        modified=now,
        obsidian_url=get_obsidian_url(filepath)
    )

def update_note(database: str, record_id: str, updates: dict, append_content: str = None) -> RecordResponse:
    """Update a note by ID"""
    db_path = DATABASES.get(database)
    if not db_path:
        raise HTTPException(status_code=400, detail=f"Unknown database: {database}")
    
    for filepath in db_path.glob("*.md"):
        content = filepath.read_text(encoding='utf-8')
        frontmatter, body = parse_frontmatter(content)
        
        if frontmatter.get("id") == record_id:
            for key, value in updates.items():
                if value is not None:
                    frontmatter[key] = value
            
            frontmatter["last_touched"] = datetime.now().isoformat()
            
            if append_content:
                body = body.rstrip() + "\n\n" + append_content
            
            fm_yaml = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
            file_content = f"---\n{fm_yaml}---\n\n{body}"
            filepath.write_text(file_content, encoding='utf-8')
            
            return RecordResponse(
                id=record_id,
                path=str(filepath.relative_to(VAULT_PATH)),
                name=frontmatter.get("name", filepath.stem),
                database=database,
                frontmatter=frontmatter,
                content=body,
                created=frontmatter.get("created", ""),
                modified=frontmatter["last_touched"],
                obsidian_url=get_obsidian_url(filepath)
            )
    
    raise HTTPException(status_code=404, detail=f"Record not found: {record_id}")

def delete_note(database: str, record_id: str) -> DeleteResponse:
    """Delete a note by ID"""
    db_path = DATABASES.get(database)
    if not db_path:
        raise HTTPException(status_code=400, detail=f"Unknown database: {database}")
    
    for filepath in db_path.glob("*.md"):
        content = filepath.read_text(encoding='utf-8')
        frontmatter, _ = parse_frontmatter(content)
        
        if frontmatter.get("id") == record_id:
            name = frontmatter.get("name", filepath.stem)
            filepath.unlink()  # Delete the file
            return DeleteResponse(
                success=True,
                deleted_id=record_id,
                deleted_name=name,
                database=database
            )
    
    raise HTTPException(status_code=404, detail=f"Record not found: {record_id}")

def find_by_id(database: str, record_id: str) -> Optional[RecordResponse]:
    """Find a record by ID"""
    db_path = DATABASES.get(database)
    if not db_path:
        return None
    
    for filepath in db_path.glob("*.md"):
        content = filepath.read_text(encoding='utf-8')
        frontmatter, body = parse_frontmatter(content)
        
        if frontmatter.get("id") == record_id:
            return RecordResponse(
                id=frontmatter.get("id", ""),
                path=str(filepath.relative_to(VAULT_PATH)),
                name=frontmatter.get("name", filepath.stem),
                database=database,
                frontmatter=frontmatter,
                content=body,
                created=frontmatter.get("created", ""),
                modified=frontmatter.get("last_touched", ""),
                obsidian_url=get_obsidian_url(filepath)
            )
    return None

def find_by_name(database: str, name: str) -> Optional[RecordResponse]:
    """Find a record by name (case-insensitive)"""
    db_path = DATABASES.get(database)
    if not db_path:
        return None
    
    name_lower = name.lower()
    for filepath in db_path.glob("*.md"):
        content = filepath.read_text(encoding='utf-8')
        frontmatter, body = parse_frontmatter(content)
        
        record_name = frontmatter.get("name", filepath.stem)
        if record_name.lower() == name_lower:
            return RecordResponse(
                id=frontmatter.get("id", ""),
                path=str(filepath.relative_to(VAULT_PATH)),
                name=record_name,
                database=database,
                frontmatter=frontmatter,
                content=body,
                created=frontmatter.get("created", ""),
                modified=frontmatter.get("last_touched", ""),
                obsidian_url=get_obsidian_url(filepath)
            )
    return None


# ============== API Endpoints ==============

@app.get("/health")
async def health_check():
    return {"status": "healthy", "vault_path": str(VAULT_PATH), "databases": list(DATABASES.keys())}


# ============== Fix Workflow (uses Inbox Log) ==============

@app.get("/pending")
async def get_pending():
    """Get the most recent 'Needs Review' inbox log entry (if any)"""
    inbox_path = DATABASES["inbox_log"]
    needs_review = []
    
    for filepath in inbox_path.glob("*.md"):
        content = filepath.read_text(encoding='utf-8')
        frontmatter, body = parse_frontmatter(content)
        
        if frontmatter.get("status") == "Needs Review":
            needs_review.append({
                "id": frontmatter.get("id"),
                "original_text": frontmatter.get("original_text", ""),
                "confidence": frontmatter.get("confidence", 0),
                "created": frontmatter.get("created", ""),
                "filepath": str(filepath)
            })
    
    if not needs_review:
        raise HTTPException(status_code=404, detail="No pending reviews")
    
    # Sort by created date, most recent first
    needs_review.sort(key=lambda x: x["created"], reverse=True)
    
    return {
        "pending": needs_review[0],
        "total_pending": len(needs_review)
    }


@app.post("/fix")
async def fix_pending(
    category: str = Query(..., description="Target category: people, projects, ideas, admin"),
    name: Optional[str] = Query(None, description="Override the auto-extracted name")
):
    """
    Fix the most recent 'Needs Review' inbox log entry.
    """
    # Validate category
    valid_categories = ["people", "projects", "ideas", "admin"]
    if category not in valid_categories:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid category. Must be one of: {valid_categories}"
        )
    
    # Find most recent "Needs Review" entry in Inbox Log
    inbox_path = DATABASES["inbox_log"]
    needs_review = []
    
    for filepath in inbox_path.glob("*.md"):
        content = filepath.read_text(encoding='utf-8')
        frontmatter, body = parse_frontmatter(content)
        
        if frontmatter.get("status") == "Needs Review":
            needs_review.append({
                "filepath": filepath,
                "frontmatter": frontmatter,
                "body": body,
                "created": frontmatter.get("created", "")
            })
    
    if not needs_review:
        raise HTTPException(status_code=404, detail="No pending review to fix")
    
    # Get most recent
    needs_review.sort(key=lambda x: x["created"], reverse=True)
    pending = needs_review[0]
    
    original_text = pending["frontmatter"].get("original_text", "")
    inbox_log_id = pending["frontmatter"].get("id", "")
    
    # Use provided name or extract from original text
    record_name = name
    if not record_name:
        clean_text = original_text.strip()
        record_name = clean_text.split('\n')[0][:50].strip()
        if not record_name:
            record_name = f"Unnamed {category} item"
    
    # Create record in target database
    record = None
    try:
        if category == "people":
            person = PersonCreate(name=record_name, context=original_text)
            record = await create_person(person)
        elif category == "projects":
            project = ProjectCreate(name=record_name, notes=original_text)
            record = await create_project(project)
        elif category == "ideas":
            idea = IdeaCreate(name=record_name, one_liner=original_text[:100], notes=original_text)
            record = await create_idea(idea)
        elif category == "admin":
            task = AdminCreate(name=record_name, notes=original_text)
            record = await create_admin_task(task)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create record: {str(e)}")
    
    # Delete the inbox log entry
    try:
        delete_note("inbox_log", inbox_log_id)
    except Exception:
        pass
    
    return {
        "success": True,
        "message": f"✅ Fixed! Saved to {category.title()}: {record.name}",
        "category": category,
        "record": record,
        "original_text": original_text
    }


# ============== Pending Delete (for delete confirmation flow) ==============

# File to store pending delete
PENDING_DELETE_FILE = VAULT_PATH / ".pending_delete.json"

@app.post("/pending_delete")
async def create_pending_delete(
    id: str = Body(...),
    database: str = Body(...),
    name: str = Body(...),
    sender: str = Body(None)
):
    """Store a single pending delete for confirmation (backwards compatible)"""
    data = {
        "id": id,
        "database": database,
        "name": name,
        "sender": sender,
        "timestamp": datetime.now().isoformat(),
        "multi": False,
        "matches": [{"id": id, "database": database, "name": name}]
    }
    
    PENDING_DELETE_FILE.write_text(json.dumps(data), encoding='utf-8')
    
    return {
        "success": True,
        "message": "Pending delete stored",
        "data": data
    }


@app.post("/pending_delete/multi")
async def create_pending_delete_multi(request: PendingDeleteMultiRequest):
    """
    Store multiple matches for selection.
    User will reply with a number (1-N) to select which to delete.
    """
    if not request.matches:
        raise HTTPException(status_code=400, detail="No matches provided")
    
    # Store all matches
    data = {
        "multi": True,
        "matches": [m.dict() for m in request.matches],
        "sender": request.sender,
        "query": request.query,
        "timestamp": datetime.now().isoformat(),
        "count": len(request.matches)
    }
    
    # Also store first match as default for backwards compatibility
    if request.matches:
        data["id"] = request.matches[0].id
        data["database"] = request.matches[0].database
        data["name"] = request.matches[0].name
    
    PENDING_DELETE_FILE.write_text(json.dumps(data), encoding='utf-8')
    
    return {
        "success": True,
        "message": f"Stored {len(request.matches)} matches for selection",
        "data": data
    }


@app.get("/pending_delete")
async def get_pending_delete():
    """Get the current pending delete (if any and not expired)"""
    if not PENDING_DELETE_FILE.exists():
        raise HTTPException(status_code=404, detail="No pending delete")
    
    try:
        data = json.loads(PENDING_DELETE_FILE.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, IOError):
        raise HTTPException(status_code=404, detail="No pending delete")
    
    # Check if expired (5 minutes)
    timestamp = datetime.fromisoformat(data["timestamp"])
    age_seconds = (datetime.now() - timestamp).total_seconds()
    
    if age_seconds > 300:  # 5 minutes
        PENDING_DELETE_FILE.unlink(missing_ok=True)
        raise HTTPException(status_code=410, detail="Pending delete expired")
    
    return data


@app.delete("/pending_delete")
async def clear_pending_delete():
    """Clear the pending delete"""
    if PENDING_DELETE_FILE.exists():
        PENDING_DELETE_FILE.unlink()
        return {"success": True, "message": "Pending delete cleared"}
    return {"success": True, "message": "No pending delete to clear"}


@app.post("/pending_delete/select/{number}")
async def select_pending_delete(number: int):
    """
    Select a match by number (1-indexed) from stored multi-match pending delete.
    """
    if not PENDING_DELETE_FILE.exists():
        raise HTTPException(status_code=404, detail="No pending delete")
    
    try:
        data = json.loads(PENDING_DELETE_FILE.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, IOError):
        raise HTTPException(status_code=404, detail="No pending delete")
    
    # Check if expired
    timestamp = datetime.fromisoformat(data["timestamp"])
    age_seconds = (datetime.now() - timestamp).total_seconds()
    
    if age_seconds > 300:
        PENDING_DELETE_FILE.unlink(missing_ok=True)
        raise HTTPException(status_code=410, detail="Pending delete expired")
    
    matches = data.get("matches", [])
    
    if not matches:
        PENDING_DELETE_FILE.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="No matches stored")
    
    # Validate number (1-indexed)
    if number < 1 or number > len(matches):
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid selection. Please choose 1-{len(matches)}"
        )
    
    # Get selected match (convert to 0-indexed)
    selected = matches[number - 1]
    
    # Execute the delete
    try:
        result = delete_note(selected["database"], selected["id"])
    except HTTPException as e:
        PENDING_DELETE_FILE.unlink(missing_ok=True)
        raise e
    
    # Clear pending delete
    PENDING_DELETE_FILE.unlink(missing_ok=True)
    
    return {
        "success": True,
        "message": f"✅ Deleted: {selected['name']} from {selected['database']}",
        "selected_number": number,
        "deleted": result
    }


@app.post("/pending_delete/execute")
async def execute_pending_delete():
    """Execute the pending delete (single match or first match if multi)"""
    if not PENDING_DELETE_FILE.exists():
        raise HTTPException(status_code=404, detail="No pending delete to execute")
    
    try:
        data = json.loads(PENDING_DELETE_FILE.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, IOError):
        raise HTTPException(status_code=404, detail="No pending delete to execute")
    
    # Check if this is a multi-match that needs selection
    if data.get("multi") and len(data.get("matches", [])) > 1:
        raise HTTPException(
            status_code=400,
            detail=f"Multiple matches found. Use /pending_delete/select/N where N is 1-{len(data['matches'])}"
        )
    
    record_id = data.get("id")
    database = data.get("database")
    name = data.get("name")
    
    if not record_id or not database:
        PENDING_DELETE_FILE.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Invalid pending delete data")
    
    # Execute the delete
    try:
        result = delete_note(database, record_id)
    except HTTPException as e:
        PENDING_DELETE_FILE.unlink(missing_ok=True)
        raise e
    
    # Clear pending delete
    PENDING_DELETE_FILE.unlink(missing_ok=True)
    
    return {
        "success": True,
        "message": f"✅ Deleted: {name} from {database}",
        "deleted": result
    }


# ============== Generic Database Endpoints ==============

@app.get("/db/all")
async def list_all_databases():
    """List all records from all content databases"""
    results = {}
    
    for db_name in CONTENT_DATABASES:
        db_path = DATABASES.get(db_name)
        if not db_path:
            continue
        
        records = []
        for filepath in db_path.glob("*.md"):
            content = filepath.read_text(encoding='utf-8')
            frontmatter, body = parse_frontmatter(content)
            
            record = {
                "id": frontmatter.get("id"),
                "name": frontmatter.get("name", filepath.stem),
                "type": frontmatter.get("type", db_name),
                "last_touched": frontmatter.get("last_touched"),
                "tags": frontmatter.get("tags", [])
            }
            
            # Add database-specific fields
            if db_name == "people":
                record["context"] = frontmatter.get("context", "")
            elif db_name == "projects":
                record["status"] = frontmatter.get("status", "")
                record["next_action"] = frontmatter.get("next_action", "")
            elif db_name == "ideas":
                record["one_liner"] = frontmatter.get("one_liner", "")
            elif db_name == "admin":
                record["due_date"] = frontmatter.get("due_date", "")
                record["status"] = frontmatter.get("status", "")
            
            records.append(record)
        
        results[db_name] = sorted(records, key=lambda x: x.get("last_touched", ""), reverse=True)
    
    return {
        "databases": results,
        "counts": {k: len(v) for k, v in results.items()},
        "total": sum(len(v) for v in results.values())
    }


@app.get("/tags")
async def list_all_tags():
    """List all unique tags across all content databases"""
    all_tags = {}
    
    for db_name in CONTENT_DATABASES:
        db_path = DATABASES.get(db_name)
        if not db_path:
            continue
        
        for filepath in db_path.glob("*.md"):
            content = filepath.read_text(encoding='utf-8')
            frontmatter, _ = parse_frontmatter(content)
            
            tags = frontmatter.get("tags", [])
            if isinstance(tags, list):
                for tag in tags:
                    if tag not in all_tags:
                        all_tags[tag] = {"count": 0, "databases": set()}
                    all_tags[tag]["count"] += 1
                    all_tags[tag]["databases"].add(db_name)
    
    # Convert sets to lists for JSON serialization
    result = []
    for tag, info in sorted(all_tags.items()):
        result.append({
            "tag": tag,
            "count": info["count"],
            "databases": sorted(list(info["databases"]))
        })
    
    return {"tags": result, "total_unique": len(result)}


@app.get("/tags/{tag}")
async def get_records_by_tag(tag: str):
    """Get all records with a specific tag"""
    results = []
    
    for db_name in CONTENT_DATABASES:
        db_path = DATABASES.get(db_name)
        if not db_path:
            continue
        
        for filepath in db_path.glob("*.md"):
            content = filepath.read_text(encoding='utf-8')
            frontmatter, _ = parse_frontmatter(content)
            
            tags = frontmatter.get("tags", [])
            if isinstance(tags, list) and tag in tags:
                results.append({
                    "id": frontmatter.get("id"),
                    "name": frontmatter.get("name", filepath.stem),
                    "database": db_name,
                    "type": frontmatter.get("type", db_name),
                    "last_touched": frontmatter.get("last_touched"),
                    "tags": tags,
                    "obsidian_url": get_obsidian_url(filepath)
                })
    
    # Sort by last_touched
    results.sort(key=lambda x: x.get("last_touched", ""), reverse=True)
    
    return {"tag": tag, "records": results, "count": len(results)}


@app.get("/recent")
async def get_recent_records(limit: int = 20):
    """Get the most recently touched records across all databases"""
    all_records = []
    
    for db_name in CONTENT_DATABASES:
        db_path = DATABASES.get(db_name)
        if not db_path:
            continue
        
        for filepath in db_path.glob("*.md"):
            content = filepath.read_text(encoding='utf-8')
            frontmatter, _ = parse_frontmatter(content)
            
            if frontmatter.get("last_touched"):
                all_records.append({
                    "id": frontmatter.get("id"),
                    "name": frontmatter.get("name", filepath.stem),
                    "database": db_name,
                    "type": frontmatter.get("type", db_name),
                    "last_touched": frontmatter.get("last_touched"),
                    "tags": frontmatter.get("tags", []),
                    "obsidian_url": get_obsidian_url(filepath)
                })
    
    # Sort by last_touched and limit
    all_records.sort(key=lambda x: x["last_touched"], reverse=True)
    
    return {"records": all_records[:limit], "total_returned": min(limit, len(all_records))}


# ---------- Generic Database Routes ----------

@app.get("/db/{database}/summary")
async def get_database_summary(database: str):
    """Get quick summary of a database - counts and names only"""
    if database not in DATABASES:
        raise HTTPException(status_code=404, detail=f"Unknown database: {database}")
    
    db_path = DATABASES[database]
    records = []
    
    for filepath in db_path.glob("*.md"):
        content = filepath.read_text(encoding='utf-8')
        frontmatter, _ = parse_frontmatter(content)
        
        records.append({
            "id": frontmatter.get("id"),
            "name": frontmatter.get("name", filepath.stem),
            "last_touched": frontmatter.get("last_touched")
        })
    
    # Sort by last_touched
    records.sort(key=lambda x: x.get("last_touched", ""), reverse=True)
    
    return {
        "database": database,
        "count": len(records),
        "records": records
    }


@app.get("/db/{database}/name/{name}")
async def get_record_by_name(database: str, name: str):
    """Get a record by name (case-insensitive)"""
    if database not in DATABASES:
        raise HTTPException(status_code=404, detail=f"Unknown database: {database}")
    
    record = find_by_name(database, name)
    if not record:
        raise HTTPException(status_code=404, detail=f"Record not found: {name}")
    
    return record


@app.get("/db/{database}/{record_id}")
async def get_record_by_id(database: str, record_id: str):
    """Get a single record by ID"""
    if database not in DATABASES:
        raise HTTPException(status_code=404, detail=f"Unknown database: {database}")
    
    record = find_by_id(database, record_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Record not found: {record_id}")
    
    return record


@app.patch("/db/{database}/{record_id}")
async def patch_record(database: str, record_id: str, updates: Dict[str, Any] = Body(...)):
    """Partial update of any record."""
    if database not in CONTENT_DATABASES:
        raise HTTPException(status_code=400, detail=f"Cannot patch database: {database}")
    
    # Extract special keys
    append_content = updates.pop("append_content", None)
    
    # Handle status enum conversion
    if "status" in updates:
        if database == "projects":
            try:
                updates["status"] = ProjectStatus(updates["status"]).value
            except ValueError:
                pass
        elif database == "admin":
            try:
                updates["status"] = AdminStatus(updates["status"]).value
            except ValueError:
                pass
    
    # Format append content with timestamp
    formatted_append = None
    if append_content:
        formatted_append = f"### {datetime.now().strftime('%Y-%m-%d %H:%M')}\n{append_content}"
    
    return update_note(database, record_id, updates, formatted_append)


# ---------- People Database ----------

@app.post("/db/people", response_model=RecordResponse)
async def create_person(person: PersonCreate):
    frontmatter = {
        "name": person.name,
        "context": person.context or "",
        "follow_ups": person.follow_ups or "",
        "tags": person.tags or [],
        "type": "person"
    }
    
    content = f"# {person.name}\n\n"
    if person.context:
        content += f"## Context\n{person.context}\n\n"
    if person.follow_ups:
        content += f"## Follow-ups\n{person.follow_ups}\n\n"
    content += "## Notes\n\n"
    
    return create_note("people", person.name, frontmatter, content)

@app.put("/db/people/{record_id}", response_model=RecordResponse)
async def update_person(record_id: str, update: PersonUpdate):
    updates = {}
    if update.context is not None:
        updates["context"] = update.context
    if update.follow_ups is not None:
        updates["follow_ups"] = update.follow_ups
    if update.tags is not None:
        updates["tags"] = update.tags
    
    append = None
    if update.append_follow_ups:
        append = f"### {datetime.now().strftime('%Y-%m-%d %H:%M')}\n{update.append_follow_ups}"
    
    return update_note("people", record_id, updates, append)

@app.delete("/db/people/{record_id}", response_model=DeleteResponse)
async def delete_person(record_id: str):
    """Delete a person record by ID"""
    return delete_note("people", record_id)

@app.get("/db/people")
async def list_people(tag: Optional[str] = None):
    results = []
    for filepath in DATABASES["people"].glob("*.md"):
        content = filepath.read_text(encoding='utf-8')
        frontmatter, _ = parse_frontmatter(content)
        
        if tag and tag not in frontmatter.get("tags", []):
            continue
            
        results.append({
            "id": frontmatter.get("id"),
            "name": frontmatter.get("name", filepath.stem),
            "context": frontmatter.get("context", ""),
            "tags": frontmatter.get("tags", []),
            "last_touched": frontmatter.get("last_touched")
        })
    
    return {"people": sorted(results, key=lambda x: x.get("last_touched", ""), reverse=True)}


# ---------- Projects Database ----------

@app.post("/db/projects", response_model=RecordResponse)
async def create_project(project: ProjectCreate):
    frontmatter = {
        "name": project.name,
        "status": project.status.value,
        "next_action": project.next_action or "",
        "tags": project.tags or [],
        "type": "project"
    }
    
    content = f"# {project.name}\n\n"
    content += f"**Status:** {project.status.value}\n\n"
    if project.next_action:
        content += f"**Next Action:** {project.next_action}\n\n"
    content += "## Notes\n"
    if project.notes:
        content += f"{project.notes}\n\n"
    content += "\n## Log\n\n"
    
    return create_note("projects", project.name, frontmatter, content)

@app.put("/db/projects/{record_id}", response_model=RecordResponse)
async def update_project(record_id: str, update: ProjectUpdate):
    updates = {}
    if update.status is not None:
        updates["status"] = update.status.value
    if update.next_action is not None:
        updates["next_action"] = update.next_action
    if update.notes is not None:
        updates["notes"] = update.notes
    if update.tags is not None:
        updates["tags"] = update.tags
    
    append = None
    if update.append_notes:
        append = f"### {datetime.now().strftime('%Y-%m-%d %H:%M')}\n{update.append_notes}"
    
    return update_note("projects", record_id, updates, append)

@app.delete("/db/projects/{record_id}", response_model=DeleteResponse)
async def delete_project(record_id: str):
    """Delete a project record by ID"""
    return delete_note("projects", record_id)

@app.get("/db/projects")
async def list_projects(status: Optional[str] = None):
    results = []
    for filepath in DATABASES["projects"].glob("*.md"):
        content = filepath.read_text(encoding='utf-8')
        frontmatter, _ = parse_frontmatter(content)
        
        if status and frontmatter.get("status") != status:
            continue
            
        results.append({
            "id": frontmatter.get("id"),
            "name": frontmatter.get("name", filepath.stem),
            "status": frontmatter.get("status"),
            "next_action": frontmatter.get("next_action", ""),
            "tags": frontmatter.get("tags", []),
            "last_touched": frontmatter.get("last_touched")
        })
    
    return {"projects": sorted(results, key=lambda x: x.get("last_touched", ""), reverse=True)}


# ---------- Ideas Database ----------

@app.post("/db/ideas", response_model=RecordResponse)
async def create_idea(idea: IdeaCreate):
    frontmatter = {
        "name": idea.name,
        "one_liner": idea.one_liner,
        "tags": idea.tags or [],
        "type": "idea"
    }
    
    content = f"# {idea.name}\n\n"
    content += f"> {idea.one_liner}\n\n"
    content += "## Notes\n"
    if idea.notes:
        content += f"{idea.notes}\n\n"
    content += "\n## Development\n\n"
    
    return create_note("ideas", idea.name, frontmatter, content)

@app.put("/db/ideas/{record_id}", response_model=RecordResponse)
async def update_idea(record_id: str, update: IdeaUpdate):
    updates = {}
    if update.one_liner is not None:
        updates["one_liner"] = update.one_liner
    if update.notes is not None:
        updates["notes"] = update.notes
    if update.tags is not None:
        updates["tags"] = update.tags
    
    append = None
    if update.append_notes:
        append = f"### {datetime.now().strftime('%Y-%m-%d %H:%M')}\n{update.append_notes}"
    
    return update_note("ideas", record_id, updates, append)

@app.delete("/db/ideas/{record_id}", response_model=DeleteResponse)
async def delete_idea(record_id: str):
    """Delete an idea record by ID"""
    return delete_note("ideas", record_id)

@app.get("/db/ideas")
async def list_ideas(tag: Optional[str] = None):
    results = []
    for filepath in DATABASES["ideas"].glob("*.md"):
        content = filepath.read_text(encoding='utf-8')
        frontmatter, _ = parse_frontmatter(content)
        
        if tag and tag not in frontmatter.get("tags", []):
            continue
            
        results.append({
            "id": frontmatter.get("id"),
            "name": frontmatter.get("name", filepath.stem),
            "one_liner": frontmatter.get("one_liner", ""),
            "tags": frontmatter.get("tags", []),
            "last_touched": frontmatter.get("last_touched")
        })
    
    return {"ideas": sorted(results, key=lambda x: x.get("last_touched", ""), reverse=True)}


# ---------- Admin Database ----------

@app.post("/db/admin", response_model=RecordResponse)
async def create_admin_task(task: AdminCreate):
    frontmatter = {
        "name": task.name,
        "due_date": task.due_date or "",
        "status": task.status.value,
        "type": "admin"
    }
    
    content = f"# {task.name}\n\n"
    if task.due_date:
        content += f"**Due:** {task.due_date}\n\n"
    content += f"**Status:** {task.status.value}\n\n"
    if task.notes:
        content += f"## Notes\n{task.notes}\n\n"
    
    return create_note("admin", task.name, frontmatter, content)

@app.put("/db/admin/{record_id}", response_model=RecordResponse)
async def update_admin_task(record_id: str, update: AdminUpdate):
    updates = {}
    if update.due_date is not None:
        updates["due_date"] = update.due_date
    if update.status is not None:
        updates["status"] = update.status.value
    if update.notes is not None:
        updates["notes"] = update.notes
    
    return update_note("admin", record_id, updates)

@app.delete("/db/admin/{record_id}", response_model=DeleteResponse)
async def delete_admin_task(record_id: str):
    """Delete an admin task by ID"""
    return delete_note("admin", record_id)

@app.get("/db/admin")
async def list_admin_tasks(status: Optional[str] = None, include_done: bool = False):
    results = []
    for filepath in DATABASES["admin"].glob("*.md"):
        content = filepath.read_text(encoding='utf-8')
        frontmatter, _ = parse_frontmatter(content)
        
        task_status = frontmatter.get("status", "Todo")
        if status and task_status != status:
            continue
        if not include_done and task_status == "Done":
            continue
            
        results.append({
            "id": frontmatter.get("id"),
            "name": frontmatter.get("name", filepath.stem),
            "due_date": frontmatter.get("due_date", ""),
            "status": task_status,
            "created": frontmatter.get("created")
        })
    
    return {"tasks": sorted(results, key=lambda x: (x.get("due_date") or "9999", x.get("created", "")))}


# ---------- Inbox Log Database ----------

@app.post("/db/inbox_log", response_model=RecordResponse)
async def create_inbox_log(log: InboxLogCreate):
    frontmatter = {
        "original_text": log.original_text,
        "filed_to": log.filed_to.value,
        "destination_name": log.destination_name,
        "destination_url": log.destination_url or "",
        "confidence": log.confidence,
        "status": log.status.value,
        "simplex_thread_ts": log.simplex_thread_ts or "",
        "obsidian_record_id": log.obsidian_record_id or "",
        "type": "inbox_log"
    }
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    name = f"Capture {timestamp}"
    
    content = f"# {name}\n\n"
    content += f"**Original:** {log.original_text}\n\n"
    content += f"**Filed to:** {log.filed_to.value} → {log.destination_name}\n\n"
    content += f"**Confidence:** {log.confidence:.0%}\n\n"
    if log.destination_url:
        content += f"**Link:** [{log.destination_name}]({log.destination_url})\n\n"
    
    return create_note("inbox_log", name, frontmatter, content)

@app.get("/db/inbox_log/{record_id}")
async def get_inbox_log_by_id(record_id: str):
    """Get a single inbox log entry by ID"""
    record = find_by_id("inbox_log", record_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Log not found: {record_id}")
    return record


@app.put("/db/inbox_log/{record_id}")
async def update_inbox_log(
    record_id: str, 
    status: Optional[str] = None, 
    notes: Optional[str] = None
):
    """Update an inbox log entry (mainly for status changes)."""
    updates = {}
    if status:
        valid_statuses = ["Filed", "Needs Review", "Fixed"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid status. Must be one of: {valid_statuses}"
            )
        updates["status"] = status
    if notes:
        updates["notes"] = notes
    
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    
    return update_note("inbox_log", record_id, updates)


@app.delete("/db/inbox_log/{record_id}", response_model=DeleteResponse)
async def delete_inbox_log(record_id: str):
    """Delete an inbox log entry by ID"""
    return delete_note("inbox_log", record_id)


@app.delete("/db/inbox_log/clear/old")
async def clear_old_inbox_logs(
    older_than_days: int = Query(default=30, description="Delete logs older than N days"),
    status: Optional[str] = Query(default="Filed", description="Only delete logs with this status")
):
    """Bulk delete old inbox logs."""
    from datetime import timedelta
    
    cutoff = (datetime.now() - timedelta(days=older_than_days)).isoformat()
    deleted = []
    
    db_path = DATABASES["inbox_log"]
    for filepath in list(db_path.glob("*.md")):
        content = filepath.read_text(encoding='utf-8')
        frontmatter, _ = parse_frontmatter(content)
        
        if status and frontmatter.get("status") != status:
            continue
        
        created = frontmatter.get("created", "")
        if created and created < cutoff:
            deleted.append({
                "id": frontmatter.get("id"),
                "original_text": frontmatter.get("original_text", "")[:50],
                "status": frontmatter.get("status"),
                "created": created
            })
            filepath.unlink()
    
    return {
        "success": True,
        "deleted_count": len(deleted),
        "older_than_days": older_than_days,
        "status_filter": status,
        "deleted": deleted
    }


@app.get("/db/inbox_log")
async def list_inbox_log(status: Optional[str] = None, limit: int = 50):
    results = []
    for filepath in sorted(DATABASES["inbox_log"].glob("*.md"), reverse=True):
        if len(results) >= limit:
            break
            
        content = filepath.read_text(encoding='utf-8')
        frontmatter, _ = parse_frontmatter(content)
        
        if status and frontmatter.get("status") != status:
            continue
            
        results.append({
            "id": frontmatter.get("id"),
            "original_text": frontmatter.get("original_text", ""),
            "filed_to": frontmatter.get("filed_to"),
            "destination_name": frontmatter.get("destination_name"),
            "confidence": frontmatter.get("confidence"),
            "status": frontmatter.get("status"),
            "created": frontmatter.get("created")
        })
    
    return {"logs": results}


# ---------- Smart Capture (Main Entry Point) ----------

@app.post("/capture")
async def smart_capture(capture: ClassifiedCapture):
    """Main capture endpoint - receives AI-classified input and routes to correct database."""
    record = None
    
    try:
        if capture.database == "people":
            existing = find_by_name("people", capture.name)
            if existing:
                update = PersonUpdate(append_follow_ups=capture.follow_ups or capture.notes)
                record = await update_person(existing.id, update)
            else:
                person = PersonCreate(
                    name=capture.name,
                    context=capture.context,
                    follow_ups=capture.follow_ups,
                    tags=capture.tags
                )
                record = await create_person(person)
                
        elif capture.database == "projects":
            existing = find_by_name("projects", capture.name)
            if existing:
                update = ProjectUpdate(next_action=capture.next_action, append_notes=capture.notes)
                record = await update_project(existing.id, update)
            else:
                project = ProjectCreate(
                    name=capture.name,
                    status=ProjectStatus(capture.status) if capture.status else ProjectStatus.ACTIVE,
                    next_action=capture.next_action,
                    notes=capture.notes,
                    tags=capture.tags
                )
                record = await create_project(project)
        elif capture.database == "ideas":
            existing = find_by_name("ideas", capture.name)
            if existing:
                # Append to existing idea
                update = IdeaUpdate(append_notes=capture.one_liner or capture.notes)
                record = await update_idea(existing.id, update)

            else:
                # Create new idea
                idea = IdeaCreate(
                    name=capture.name,
                    one_liner=capture.one_liner or capture.original_text[:100],
                    notes=capture.notes,
                    tags=capture.tags
                )
                record = await create_idea(idea)
        elif capture.database == "admin":
            task = AdminCreate(
                name=capture.name,
                due_date=capture.due_date,
                status=AdminStatus.TODO,
                notes=capture.notes
            )
            record = await create_admin_task(task)
            
        else:  # needs_review
            log = InboxLogCreate(
                original_text=capture.original_text,
                filed_to=FiledTo.NEEDS_REVIEW,
                destination_name="Needs Manual Review",
                confidence=capture.confidence,
                status=InboxStatus.NEEDS_REVIEW,
                simplex_thread_ts=capture.simplex_thread_ts
            )
            record = await create_inbox_log(log)
            return {
                "success": True,
                "needs_review": True,
                "record": record,
                "message": f"⚠️ Couldn't confidently classify. Saved to Inbox for review."
            }
        
        # Log successful capture
        filed_to_map = {"people": FiledTo.PEOPLE, "projects": FiledTo.PROJECTS, "ideas": FiledTo.IDEAS, "admin": FiledTo.ADMIN}
        log = InboxLogCreate(
            original_text=capture.original_text,
            filed_to=filed_to_map.get(capture.database, FiledTo.NEEDS_REVIEW),
            destination_name=record.name,
            destination_url=record.obsidian_url,
            confidence=capture.confidence,
            status=InboxStatus.FILED,
            simplex_thread_ts=capture.simplex_thread_ts,
            obsidian_record_id=record.id
        )
        await create_inbox_log(log)
        
        return {
            "success": True,
            "needs_review": False,
            "record": record,
            "message": f"✅ Saved to {capture.database.title()}: {record.name}"
        }
        
    except Exception as e:
        log = InboxLogCreate(
            original_text=capture.original_text,
            filed_to=FiledTo.NEEDS_REVIEW,
            destination_name=f"Error: {str(e)[:50]}",
            confidence=capture.confidence,
            status=InboxStatus.NEEDS_REVIEW,
            simplex_thread_ts=capture.simplex_thread_ts
        )
        await create_inbox_log(log)
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Search ----------

@app.post("/search")
async def search_all(query: str, databases: Optional[List[str]] = None, limit: int = 10):
    results = []
    query_lower = query.lower()
    search_dbs = databases or list(DATABASES.keys())
    
    for db_name in search_dbs:
        db_path = DATABASES.get(db_name)
        if not db_path:
            continue
            
        for filepath in db_path.glob("*.md"):
            content = filepath.read_text(encoding='utf-8')
            frontmatter, body = parse_frontmatter(content)
            
            searchable = f"{frontmatter.get('name', '')} {body} {' '.join(str(v) for v in frontmatter.values())}"
            
            if query_lower in searchable.lower():
                pos = body.lower().find(query_lower)
                if pos >= 0:
                    start = max(0, pos - 30)
                    end = min(len(body), pos + len(query) + 50)
                    context = body[start:end]
                else:
                    context = body[:80] if body else ""
                
                results.append({
                    "database": db_name,
                    "id": frontmatter.get("id"),
                    "name": frontmatter.get("name", filepath.stem),
                    "context": f"...{context}..." if context else "",
                    "path": str(filepath.relative_to(VAULT_PATH)),
                    "obsidian_url": get_obsidian_url(filepath)
                })
                
                if len(results) >= limit:
                    return {"results": results, "truncated": True}
    
    return {"results": results, "truncated": False}


# ---------- Daily Notes ----------

@app.post("/daily/append")
async def append_to_daily(text: str, heading: Optional[str] = None):
    today = date.today().strftime("%Y-%m-%d")
    filepath = DATABASES["daily"] / f"{today}.md"
    timestamp = datetime.now().strftime("%H:%M")
    
    if heading:
        entry = f"\n\n## {heading}\n*{timestamp}*\n\n{text}"
    else:
        entry = f"\n\n### {timestamp}\n{text}"
    
    if filepath.exists():
        content = filepath.read_text(encoding='utf-8')
        frontmatter, body = parse_frontmatter(content)
        new_body = body.rstrip() + entry
        frontmatter["last_touched"] = datetime.now().isoformat()
        fm_yaml = yaml.dump(frontmatter, default_flow_style=False)
        new_content = f"---\n{fm_yaml}---\n\n{new_body}"
    else:
        frontmatter = {"created": datetime.now().isoformat(), "last_touched": datetime.now().isoformat(), "type": "daily"}
        fm_yaml = yaml.dump(frontmatter, default_flow_style=False)
        new_content = f"---\n{fm_yaml}---\n\n# {today}" + entry
    
    filepath.write_text(new_content, encoding='utf-8')
    return {"success": True, "path": str(filepath.relative_to(VAULT_PATH)), "obsidian_url": get_obsidian_url(filepath)}


# ---------- Stats ----------

@app.get("/stats")
async def get_stats():
    stats = {}
    for db_name, db_path in DATABASES.items():
        stats[db_name] = len(list(db_path.glob("*.md")))
    
    recent = []
    for db_name, db_path in DATABASES.items():
        for filepath in db_path.glob("*.md"):
            content = filepath.read_text(encoding='utf-8')
            frontmatter, _ = parse_frontmatter(content)
            if frontmatter.get("last_touched"):
                recent.append({"database": db_name, "name": frontmatter.get("name", filepath.stem), "last_touched": frontmatter["last_touched"]})
    
    recent.sort(key=lambda x: x["last_touched"], reverse=True)
    return {"counts": stats, "total": sum(stats.values()), "recent_activity": recent[:10]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
