from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from aai_app.config import AppConfig


@dataclass
class ChatMessage:
    role: str
    content: str
    timestamp: str


@dataclass
class ChatSession:
    session_id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[ChatMessage]


class MemoryStore:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.sessions_dir = config.logs_dir / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = config.logs_dir / "session-state.json"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _session_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.json"

    def create_session(self, title: str = "New chat") -> ChatSession:
        now = self._now()
        session = ChatSession(
            session_id=uuid4().hex[:12],
            title=title,
            created_at=now,
            updated_at=now,
            messages=[],
        )
        self.save_session(session)
        self.set_active_session(session.session_id)
        return session

    def save_session(self, session: ChatSession) -> None:
        session.updated_at = self._now()
        payload = {
            **asdict(session),
            "messages": [asdict(message) for message in session.messages],
        }
        self._session_path(session.session_id).write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    def load_session(self, session_id: str) -> ChatSession:
        data = json.loads(self._session_path(session_id).read_text(encoding="utf-8"))
        messages = [ChatMessage(**item) for item in data.get("messages", [])]
        return ChatSession(
            session_id=data["session_id"],
            title=data["title"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            messages=messages,
        )

    def list_sessions(self) -> list[ChatSession]:
        sessions: list[ChatSession] = []
        for path in sorted(self.sessions_dir.glob("*.json"), reverse=True):
            try:
                sessions.append(self.load_session(path.stem))
            except Exception:
                continue
        return sorted(sessions, key=lambda item: item.updated_at, reverse=True)

    def set_active_session(self, session_id: str) -> None:
        self.state_path.write_text(
            json.dumps({"active_session_id": session_id}, indent=2),
            encoding="utf-8",
        )

    def get_active_session(self) -> ChatSession:
        if self.state_path.exists():
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            session_id = data.get("active_session_id")
            if session_id and self._session_path(session_id).exists():
                return self.load_session(session_id)
        sessions = self.list_sessions()
        if sessions:
            self.set_active_session(sessions[0].session_id)
            return sessions[0]
        return self.create_session()

    def resolve_session_reference(self, reference: str | None) -> ChatSession:
        sessions = self.list_sessions()
        if not sessions:
            raise ValueError("No saved sessions are available yet.")
        if not reference or reference.lower() in {"latest", "last", "recent"}:
            session = sessions[0]
            self.set_active_session(session.session_id)
            return session

        candidate = reference.strip()
        if candidate.isdigit():
            index = int(candidate) - 1
            if 0 <= index < len(sessions):
                session = sessions[index]
                self.set_active_session(session.session_id)
                return session
            raise ValueError(f"Session number {candidate} is out of range.")

        for session in sessions:
            if session.session_id.startswith(candidate):
                self.set_active_session(session.session_id)
                return session

        lowered = candidate.lower()
        for session in sessions:
            if lowered in session.title.lower():
                self.set_active_session(session.session_id)
                return session

        raise ValueError(
            "Could not find that session. Use /sessions to see the latest saved conversations."
        )

    def append_message(self, session: ChatSession, role: str, content: str) -> ChatSession:
        session.messages.append(
            ChatMessage(role=role, content=content, timestamp=self._now())
        )
        if session.title == "New chat" and role == "user":
            session.title = content.strip()[:48] or "Chat"
        self.save_session(session)
        self.set_active_session(session.session_id)
        return session

    def render_session_transcript(self, session: ChatSession) -> str:
        lines: list[str] = []
        for message in session.messages:
            role = message.role.capitalize()
            lines.append(f"{role}: {message.content.strip()}")
        return "\n\n".join(lines).strip()
