"""Notes management tool for MCP server."""

from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass, asdict


@dataclass
class Note:
    """Represents a note."""
    id: str
    title: str
    content: str
    created_at: str


class NotesManager:
    """Manages in-memory note storage."""
    
    def __init__(self):
        self._notes: Dict[str, Note] = {}
        self._counter = 1
    
    def create_note(self, title: str, content: str) -> dict:
        """Create a new note."""
        note_id = f"note-{self._counter}"
        self._counter += 1
        
        note = Note(
            id=note_id,
            title=title,
            content=content,
            created_at=datetime.now().isoformat()
        )
        
        self._notes[note_id] = note
        return asdict(note)
    
    def get_note(self, note_id: str) -> dict:
        """Retrieve a note by ID."""
        note = self._notes.get(note_id)
        if not note:
            raise ValueError(f"Note with id '{note_id}' not found")
        return asdict(note)
    
    def list_notes(self) -> List[dict]:
        """List all notes."""
        return [asdict(note) for note in self._notes.values()]
    
    def delete_note(self, note_id: str) -> dict:
        """Delete a note by ID."""
        if note_id not in self._notes:
            raise ValueError(f"Note with id '{note_id}' not found")
        
        del self._notes[note_id]
        return {
            "success": True,
            "message": f"Note '{note_id}' deleted successfully"
        }


# Global instance
notes_manager = NotesManager()
