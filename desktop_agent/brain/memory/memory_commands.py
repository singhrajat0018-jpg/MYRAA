"""
MYRAA Memory 2.0 — M10: Explicit Memory Command System.

Parses natural-language (English + Hinglish) memory commands and executes them
against the authoritative UnifiedMemoryManager.

Supported intents:

    REMEMBER      "remember that I prefer Hinglish" / "yaad rakh"
    RECALL        "what do you remember about X" / "kya yaad hai"
    UPDATE        "update the memory about X" / "change what you remember"
    FORGET        "forget my preference about X" / "bhool jao"
    LIST          "show my memories about X" / "memories dikhao"
    CLEAR_SCOPE   "forget this project's memories" / "clear task memory"

Rules:
    - Every operation goes through UnifiedMemoryManager (single authority).
    - Explicit user commands carry Provenance.USER_EXPLICIT and use
      USER_DEFINED retention (they override ordinary retention policy).
    - Scope is respected; project/task clears only touch that scope+id.
    - Sensitivity filtering: secret-like content is rejected, never stored,
      and never echoed back.
    - Ambiguous references produce a clarification question, never a blind
      delete. Nonexistent targets are reported, not invented.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


# ==========================================================
# Command model
# ==========================================================

@dataclass
class MemoryCommand:
    """A parsed explicit memory command."""

    operation: str                      # REMEMBER / RECALL / UPDATE / FORGET / LIST / CLEAR_SCOPE
    content: str = ""                   # fact/preference to store (REMEMBER/UPDATE)
    subject: str = ""                   # target of RECALL/FORGET/UPDATE/LIST
    scope: Optional[str] = None         # GLOBAL/USER/PROJECT/TASK/CONVERSATION/SESSION hint
    project_id: Optional[str] = None
    task_id: Optional[str] = None
    conversation_id: Optional[str] = None
    memory_type: Optional[str] = None   # SEMANTIC / PREFERENCE / EPISODIC ...
    is_command: bool = False
    needs_clarification: bool = False
    reason: str = ""
    matched_phrase: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "content": self.content,
            "subject": self.subject,
            "scope": self.scope,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "conversation_id": self.conversation_id,
            "memory_type": self.memory_type,
            "needs_clarification": self.needs_clarification,
            "reason": self.reason,
        }


@dataclass
class MemoryCommandResult:
    """Result of executing a memory command."""

    success: bool
    message: str
    operation: str = ""
    affected_ids: List[str] = field(default_factory=list)
    records: List[Any] = field(default_factory=list)
    needs_clarification: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "operation": self.operation,
            "affected_ids": self.affected_ids,
            "needs_clarification": self.needs_clarification,
            "records": [
                {
                    "id": r.id,
                    "type": str(r.type),
                    "content": r.content,
                    "scope": str(r.scope),
                    "importance": r.importance,
                    "confidence": r.confidence,
                }
                for r in self.records
            ],
        }


# ==========================================================
# Parser
# ==========================================================

class MemoryCommandParser:
    """
    Rule-based parser for English + Hinglish memory commands.

    Prefers anchored trigger phrases to avoid false positives on casual speech
    (e.g. "I remember you from yesterday" is not a store command).
    """

    # --- REMEMBER triggers (English + Hinglish) --------------------------
    _REMEMBER_PREFIX = (
        r"(?:please\s+)?(?:"
        r"remember|"
        r"yaad\s+(?:rakh|rakho|rakhna|rakhiye|kar|karo)|"
        r"dhyaan\s+rakh|"
        r"note(?:\s+down\s+)?|"
        r"save\s+this|"
        r"store\s+this|"
        r"likh\s+le|"
        r"yaad\s+rkh"
        r")"
    )

    # --- FORGET triggers ------------------------------------------------
    _FORGET_PREFIX = (
        r"(?:please\s+)?(?:"
        r"forget|"
        r"yaad\s+mat\s+(?:rakh|rakho|rakhna)|"
        r"mat\s+bhool|"
        r"bhool\s+(?:ja|jao|jaiye)|"
        r"delete\s+(?:the\s+)?memory\s+about|"
        r"remove\s+(?:the\s+)?memory\s+about|"
        r"hata\s+do"
        r")"
    )

    # --- RECALL triggers ------------------------------------------------
    _RECALL_PATTERNS = [
        r"what\s+do\s+you\s+(?:remember|recall|know)\s+about\s+(.+?)\s*\??$",
        r"do\s+you\s+(?:remember|recall|know)\s+(.+?)\s*\??$",
        r"what\s+do\s+you\s+(?:remember|recall)\s*\??$",
        r"what\s+memories\s+do\s+you\s+have\s+about\s+(.+?)\s*\??$",
        r"(.+?)\s+ke\s+baare\s+mein\s+kya\s+yaad\s+hai\s*\??$",
        r"kya\s+yaad\s+hai\s+(.+?)\s+ke\s+baare\s+mein\s*\??$",
        r"(.+?)\s+ke\s+baare\s+mein\s+kya\s+pata\s+hai\s*\??$",
        r"yaad\s+hai\s+kya\s+(.+?)\s*\??$",
        r"kya\s+yaad\s+rakh\s+ho\s+humne\s*(.+?)\s*\??$",
    ]

    # --- UPDATE / CHANGE ------------------------------------------------
    _UPDATE_PATTERNS = [
        r"update\s+(?:the\s+)?memory\s+about\s+(.+?)\s+(?:to|with|that)\s+(.+?)\s*$",
        r"change\s+what\s+you\s+remember\s+about\s+(.+?)\s+to\s+(.+?)\s*$",
        r"change\s+(?:the\s+)?memory\s+about\s+(.+?)\s*$",
        r"update\s+(?:the\s+)?memory\s+about\s+(.+?)\s*$",
        r"update\s+that\s+(.+?)\s*$",
    ]

    # --- LIST / SHOW ----------------------------------------------------
    _LIST_PATTERNS = [
        r"show\s+(?:me\s+)?(?:all\s+)?(?:my\s+)?memories\s+about\s+(.+?)\s*$",
        r"list\s+(?:all\s+)?(?:my\s+)?memories\s+about\s+(.+?)\s*$",
        r"show\s+(?:me\s+)?(?:all\s+)?(?:my\s+)?memories\s*$",
        r"list\s+(?:all\s+)?(?:my\s+)?memories\s*$",
        r"memories\s+dikhao\s*(.+?)?\s*$",
        r"kya\s+memories\s+(?:hain|hai)\s*(.+?)?\s*$",
        r"what\s+do\s+you\s+know\s+overall\s*$",
    ]

    # --- CLEAR_SCOPE ----------------------------------------------------
    _CLEAR_SCOPE_PATTERNS = [
        (r"forget\s+this\s+project(?:'s)?\s*(?:memories|memory)\s*$", "PROJECT"),
        (r"clear\s+(?:this\s+)?project(?:'s)?\s*(?:memories|memory)\s*$", "PROJECT"),
        (r"delete\s+this\s+project(?:'s)?\s*(?:memories|memory)\s*$", "PROJECT"),
        (r"forget\s+this\s+task(?:'s)?\s*(?:memories|memory)\s*$", "TASK"),
        (r"clear\s+(?:this\s+)?task(?:'s)?\s*(?:memories|memory)\s*$", "TASK"),
        (r"delete\s+this\s+task(?:'s)?\s*(?:memories|memory)\s*$", "TASK"),
        (r"project\s+ki\s+(?:saari\s+)?memories\s+bhool\s+jao\s*$", "PROJECT"),
        (r"task\s+ki\s+(?:saari\s+)?memories\s+bhool\s+jao\s*$", "TASK"),
    ]

    # --- REMEMBER content extraction ------------------------------------
    _REMEMBER_CONTENT_PATTERNS = [
        # "remember that <content>"
        r"^\s*" + _REMEMBER_PREFIX + r"\s+(?:that\s+|ki\s+)?(.+?)\s*$",
        # "yaad rakh <content>"
        r"^\s*" + _REMEMBER_PREFIX + r"\s+(?:ki\s+|that\s+)?(.+?)\s*$",
    ]

    # "remember this" / "yaad rakh lo" / "note this" — no explicit content.
    _REMEMBER_THIS = re.compile(
        r"^\s*" + _REMEMBER_PREFIX + r"\s+(?:this|it|yeh|yahan|kuch)\s*$",
        re.IGNORECASE,
    )
    _REMEMBER_NAKED = re.compile(
        r"^\s*" + _REMEMBER_PREFIX + r"\s*$",
        re.IGNORECASE,
    )

    # FORGET subject extraction
    _FORGET_SUBJECT_PATTERNS = [
        r"^\s*" + _FORGET_PREFIX + r"\s+(?:that\s+)?(.+?)\s*$",
    ]
    _FORGET_NAKED = re.compile(
        r"^\s*" + _FORGET_PREFIX + r"\s*$",
        re.IGNORECASE,
    )

    # subject type hints
    _PREFERENCE_HINT = re.compile(r"\bprefer|preference|pasand\b", re.IGNORECASE)

    # --- M11 lifecycle commands -----------------------------------------
    # (op, prefix-regex) — each captures the target subject after the phrase.
    _LIFECYCLE_PATTERNS = [
        ("ARCHIVE", r"archive\s+(?:the\s+)?memory\s+about"),
        ("ARCHIVE", r"archive\s+(?:that\s+)?(?:the\s+)?(?:memory\s+)?(?:of\s+|about\s+)?"),
        ("BURY", r"bury\s+(?:the\s+)?memory\s+about"),
        ("BURY", r"bury\s+(?:that\s+)?(?:the\s+)?(?:memory\s+)?"),
        ("RETRACT", r"retract\s+(?:the\s+)?memory\s+about"),
        ("RETRACT", r"retract\s+(?:that\s+)?(?:the\s+)?(?:memory\s+)?"),
        ("EXPIRE", r"expire\s+(?:the\s+)?memory\s+about"),
        ("EXPIRE", r"expire\s+(?:that\s+)?(?:the\s+)?(?:memory\s+)?"),
        ("RESTORE", r"restore\s+(?:the\s+)?memory\s+about"),
        ("RESTORE", r"restore\s+(?:that\s+)?(?:the\s+)?(?:memory\s+)?"),
    ]

    def parse(self, text: str, context: Optional[Any] = None) -> MemoryCommand:
        """Parse a user utterance into a MemoryCommand (English + Hinglish)."""
        if not text or not text.strip():
            return MemoryCommand(operation="NONE")

        raw = text.strip()

        # Context hints (project/task/conversation ids come from the caller).
        project_id = getattr(context, "project_id", None) or None
        task_id = getattr(context, "task_id", None) or None
        conversation_id = getattr(context, "conversation_id", None) or None

        # --- CLEAR_SCOPE ------------------------------------------------
        for pattern, scope in self._CLEAR_SCOPE_PATTERNS:
            if re.search(pattern, raw, re.IGNORECASE):
                if scope == "PROJECT" and not project_id:
                    return MemoryCommand(
                        operation="CLEAR_SCOPE", is_command=True,
                        needs_clarification=True,
                        reason="no_project_id",
                    )
                if scope == "TASK" and not task_id:
                    return MemoryCommand(
                        operation="CLEAR_SCOPE", is_command=True,
                        needs_clarification=True,
                        reason="no_task_id",
                    )
                return MemoryCommand(
                    operation="CLEAR_SCOPE", is_command=True, scope=scope,
                    project_id=project_id, task_id=task_id,
                    conversation_id=conversation_id, matched_phrase=pattern,
                )

        # --- RECALL -----------------------------------------------------
        for pattern in self._RECALL_PATTERNS:
            match = re.match(pattern, raw, re.IGNORECASE)
            if match:
                subject = (match.group(1) or "").strip() if match.lastindex else ""
                return MemoryCommand(
                    operation="RECALL", is_command=True, subject=subject,
                    project_id=project_id, task_id=task_id,
                    conversation_id=conversation_id, matched_phrase=pattern,
                )

        # --- LIST / SHOW ------------------------------------------------
        for pattern in self._LIST_PATTERNS:
            match = re.match(pattern, raw, re.IGNORECASE)
            if match:
                subject = match.group(1).strip() if match.lastindex and match.group(1) else ""
                return MemoryCommand(
                    operation="LIST", is_command=True, subject=subject,
                    project_id=project_id, task_id=task_id,
                    conversation_id=conversation_id, matched_phrase=pattern,
                )

        # --- UPDATE / CHANGE --------------------------------------------
        for idx, pattern in enumerate(self._UPDATE_PATTERNS):
            match = re.match(pattern, raw, re.IGNORECASE)
            if match:
                groups = match.groups()
                if idx == 4:  # "update that <content>" — single group is content
                    content = groups[0].strip() if groups else ""
                    subject = ""
                elif len(groups) >= 2:
                    subject = (groups[0] or "").strip()
                    content = (groups[-1] or "").strip()
                else:
                    subject = (groups[0] or "").strip()
                    content = ""
                return MemoryCommand(
                    operation="UPDATE", is_command=True, subject=subject,
                    content=content, project_id=project_id, task_id=task_id,
                    conversation_id=conversation_id, matched_phrase=pattern,
                )

        # --- M11 lifecycle commands ------------------------------------
        for op, prefix in self._LIFECYCLE_PATTERNS:
            match = re.match(rf"^\s*(?:please\s+)?{prefix}\s+(.+?)\s*$", raw, re.IGNORECASE)
            if match:
                subject = match.group(1).strip()
                return MemoryCommand(
                    operation=op, is_command=True, subject=subject,
                    project_id=project_id, task_id=task_id,
                    conversation_id=conversation_id, matched_phrase=prefix,
                )

        # --- FORGET -----------------------------------------------------
        for pattern in self._FORGET_SUBJECT_PATTERNS:
            match = re.match(pattern, raw, re.IGNORECASE)
            if match:
                subject = (match.group(1) or "").strip()
                return MemoryCommand(
                    operation="FORGET", is_command=True, subject=subject,
                    project_id=project_id, task_id=task_id,
                    conversation_id=conversation_id, matched_phrase=pattern,
                )
        if self._FORGET_NAKED.match(raw):
            return MemoryCommand(
                operation="FORGET", is_command=True,
                needs_clarification=True, reason="no_subject",
                matched_phrase="forget",
            )

        # --- REMEMBER ---------------------------------------------------
        if self._REMEMBER_THIS.match(raw):
            return MemoryCommand(
                operation="REMEMBER", is_command=True,
                needs_clarification=True, reason="no_content",
                matched_phrase="remember",
            )
        if self._REMEMBER_NAKED.match(raw):
            return MemoryCommand(
                operation="REMEMBER", is_command=True,
                needs_clarification=True, reason="no_content",
                matched_phrase="remember",
            )
        for pattern in self._REMEMBER_CONTENT_PATTERNS:
            match = re.match(pattern, raw, re.IGNORECASE)
            if match:
                content = (match.group(1) or "").strip().rstrip(".")
                if content:
                    mem_type = "PREFERENCE" if self._PREFERENCE_HINT.search(content) else "SEMANTIC"
                    return MemoryCommand(
                        operation="REMEMBER", is_command=True, content=content,
                        memory_type=mem_type, project_id=project_id,
                        task_id=task_id, conversation_id=conversation_id,
                        matched_phrase=pattern,
                    )

        return MemoryCommand(operation="NONE")


# ==========================================================
# Engine
# ==========================================================

class MemoryCommandEngine:
    """Executes parsed memory commands against UnifiedMemoryManager."""

    def __init__(self, manager: Any):
        from desktop_agent.brain.memory.unified_manager import UnifiedMemoryManager
        if not isinstance(manager, UnifiedMemoryManager):
            raise TypeError("MemoryCommandEngine requires a UnifiedMemoryManager")
        self.manager = manager
        self.parser = MemoryCommandParser()

    # ------------------------------------------------------------------

    def execute(self, command: MemoryCommand,
                context: Optional[Any] = None) -> MemoryCommandResult:
        if not command.is_command:
            return MemoryCommandResult(success=False, operation="NONE",
                                       message="That doesn't look like a memory command.")
        if command.needs_clarification:
            return self._clarify(command)

        handler = getattr(self, f"_do_{command.operation.lower()}", None)
        if handler is None:
            return MemoryCommandResult(success=False, operation=command.operation,
                                       message=f"Unsupported operation: {command.operation}")
        return handler(command, context)

    # ------------------------------------------------------------------

    def _clarify(self, command: MemoryCommand) -> MemoryCommandResult:
        messages = {
            "no_content": (
                "Kya yaad rakhna hai? Batao ki main kya store karoon. "
                "(What should I remember? Tell me what to store.)"
            ),
            "no_subject": (
                "Kis chiz ke baare mein bhoolna hai? Koi subject batao. "
                "(What should I forget? Give me a subject.)"
            ),
            "no_project_id": (
                "Kis project ki memories saaf karni hain? Project context nahi mila. "
                "(Which project's memories? I don't have the project context.)"
            ),
            "no_task_id": (
                "Kis task ki memories saaf karni hain? Task context nahi mila. "
                "(Which task's memories? I don't have the task context.)"
            ),
        }
        message = messages.get(command.reason, "Please clarify what you'd like me to do.")
        return MemoryCommandResult(success=True, operation=command.operation,
                                   message=message, needs_clarification=True)

    # ------------------------------------------------------------------
    # REMEMBER
    # ------------------------------------------------------------------

    def _do_remember(self, command: MemoryCommand, context: Any) -> MemoryCommandResult:
        from desktop_agent.brain.memory.unified_model import (
            MemoryRecord, MemoryType, MemoryScope, MemoryStatus,
            RetentionPolicy, Provenance,
        )
        from desktop_agent.brain.memory.persistence import is_sensitive_text

        content = (command.content or "").strip()
        if not content:
            return self._clarify(command)
        if is_sensitive_text(content):
            log.warning("[Memory][Security] REMEMBER rejected sensitive content")
            return MemoryCommandResult(
                success=False, operation="REMEMBER",
                message=("Sorry, that looks like a secret (password/token/key) "
                         "and I never store secrets. Koi normal cheez batao."),
            )

        mem_type = MemoryType.PREFERENCE if command.memory_type == "PREFERENCE" \
            else MemoryType.SEMANTIC
        scope = MemoryScope.PROJECT if (command.scope == "PROJECT" or
                                        (command.project_id and "project" in content.lower())) \
            else MemoryScope.USER

        record = MemoryRecord(
            type=mem_type,
            content=content,
            summary=content[:120],
            source="user_command",
            scope=scope,
            project_id=command.project_id if scope == MemoryScope.PROJECT else None,
            task_id=command.task_id if scope in (MemoryScope.PROJECT, MemoryScope.TASK) else None,
            conversation_id=command.conversation_id,
            importance=0.9,
            confidence=1.0,
            retention_policy=RetentionPolicy.USER_DEFINED,
            status=MemoryStatus.ACTIVE,
            provenance=Provenance.USER_EXPLICIT,
            tags={"user_explicit"},
        )
        ok = self.manager.remember(record)
        if not ok:
            return MemoryCommandResult(success=False, operation="REMEMBER",
                                       message="Yaad nahi kar paya — memory store failed. (Could not remember.)")
        kind = "preference" if mem_type == MemoryType.PREFERENCE else "fact"
        return MemoryCommandResult(
            success=True, operation="REMEMBER",
            message=f"Got it! Yaad rakh liya: \"{content}\" ({kind}, USER scope).",
            affected_ids=[record.id], records=[record],
        )

    # ------------------------------------------------------------------
    # RECALL
    # ------------------------------------------------------------------

    def _find_candidates(self, query: str, limit: int = 10) -> List[Any]:
        if not query:
            return []
        try:
            results = self.manager.recall_by_content(query, limit=limit)
        except Exception:
            return []
        # Strict lexical gate: a command target must share a meaningful token
        # with the content (or be a substring). The fuzzy retrieval can return
        # weak semantic matches that are unsafe for destructive operations.
        return [r for r in results if self._score_query(query, r.content) > 0.0]

    def _do_recall(self, command: MemoryCommand, context: Any) -> MemoryCommandResult:
        subject = (command.subject or "").strip()

        from desktop_agent.brain.memory.unified_model import MemoryScope

        if command.scope == "PROJECT" and command.project_id:
            records = self.manager.recall_by_scope(
                MemoryScope.PROJECT, project_id=command.project_id, limit=15)
        elif command.scope == "TASK" and command.task_id:
            records = self.manager.recall_by_scope(
                MemoryScope.TASK, task_id=command.task_id, limit=15)
        elif subject:
            records = self._find_candidates(subject, limit=10)
        else:
            records = self.manager.get_all_active()[-10:]

        if not records:
            if subject:
                return MemoryCommandResult(
                    success=True, operation="RECALL",
                    message=(f"I don't remember anything about \"{subject}\" yet. "
                             "Abhi tak kuch yaad nahi hai."))
            return MemoryCommandResult(
                success=True, operation="RECALL",
                message="Meri memory khali hai abhi. (My memory is empty right now.)")

        lines = [self._format_record(r) for r in records[:10]]
        head = f"Yaad hai — about \"{subject}\":\n" if subject else "Yaad hai:\n"
        return MemoryCommandResult(
            success=True, operation="RECALL",
            message=head + "\n".join(lines),
            records=records[:10],
            affected_ids=[r.id for r in records[:10]],
        )

    def _format_record(self, record: Any) -> str:
        snippet = (record.content or record.summary or "")[:120]
        return f"• {snippet} [{record.type.value}/{record.scope.value} conf={record.confidence:.2f}]"

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------

    def _do_update(self, command: MemoryCommand, context: Any) -> MemoryCommandResult:
        from desktop_agent.brain.memory.unified_model import (
            MemoryRecord, MemoryScope, MemoryStatus, RetentionPolicy, Provenance,
        )
        from desktop_agent.brain.memory.persistence import is_sensitive_text

        subject = (command.subject or "").strip()
        content = (command.content or "").strip()

        # "update that <content>" — subject may be empty; use content as both.
        if not subject:
            subject = content[:40]
        if not content:
            return MemoryCommandResult(
                success=True, operation="UPDATE", needs_clarification=True,
                message="Update karke kya banaoon? Naya value batao. (What's the new value?)")

        candidates = self._find_candidates(subject, limit=5)
        if not candidates:
            # Nothing to update -> store as a new fact instead.
            cmd = MemoryCommand(operation="REMEMBER", is_command=True,
                                content=content, memory_type=command.memory_type,
                                project_id=command.project_id,
                                task_id=command.task_id,
                                conversation_id=command.conversation_id)
            result = self._do_remember(cmd, context)
            result.operation = "UPDATE"
            result.message = (f"I didn't find a memory about \"{subject}\", "
                              "so I stored it as new: \"{content}\". (Pehle koi memory nahi mili.)")
            return result

        target = max(candidates, key=lambda r: getattr(r, "confidence", 0.0))
        if is_sensitive_text(content):
            return MemoryCommandResult(
                success=False, operation="UPDATE",
                message="Sorry, that looks like a secret — I never store secrets.")

        updated = MemoryRecord(
            type=target.type,
            content=content,
            summary=content[:120],
            source="user_update",
            scope=target.scope,
            project_id=target.project_id,
            task_id=target.task_id,
            conversation_id=target.conversation_id,
            importance=max(0.9, getattr(target, "importance", 0.7)),
            confidence=1.0,
            retention_policy=RetentionPolicy.USER_DEFINED,
            status=MemoryStatus.ACTIVE,
            provenance=Provenance.USER_EXPLICIT,
            id=target.id,
        )
        ok = self.manager.remember(updated)
        if not ok:
            return MemoryCommandResult(success=False, operation="UPDATE",
                                       message="Update nahi ho paya. (Could not update.)")
        return MemoryCommandResult(
            success=True, operation="UPDATE",
            message=f"Update kar diya: \"{content}\" (was about \"{subject}\").",
            affected_ids=[target.id], records=[updated],
        )

    # ------------------------------------------------------------------
    # M11 lifecycle commands (ARCHIVE/BURY/RETRACT/EXPIRE/RESTORE)
    # ------------------------------------------------------------------

    def _do_archive(self, command: MemoryCommand, context: Any) -> MemoryCommandResult:
        return self._lifecycle_apply(command, "ARCHIVE")

    def _do_bury(self, command: MemoryCommand, context: Any) -> MemoryCommandResult:
        return self._lifecycle_apply(command, "BURY")

    def _do_retract(self, command: MemoryCommand, context: Any) -> MemoryCommandResult:
        return self._lifecycle_apply(command, "RETRACT")

    def _do_expire(self, command: MemoryCommand, context: Any) -> MemoryCommandResult:
        return self._lifecycle_apply(command, "EXPIRE")

    def _do_restore(self, command: MemoryCommand, context: Any) -> MemoryCommandResult:
        return self._lifecycle_apply(command, "RESTORE")

    def _lifecycle_apply(self, command: MemoryCommand, operation: str) -> MemoryCommandResult:
        subject = (command.subject or "").strip()
        if not subject:
            return self._clarify(command)

        if operation == "RESTORE":
            # Non-active records are the restore targets.
            all_records = self.manager.get_all()
            candidates = [r for r in all_records
                          if getattr(r, "status", None) is not None
                          and r.status.value != "active"
                          and self._score_query(subject, r.content) > 0.0]
        else:
            candidates = self._find_candidates(subject, limit=10)

        if not candidates:
            if operation == "RESTORE":
                return MemoryCommandResult(
                    success=True, operation=operation,
                    message=(f"Koi archived/expired memory nahi mili about \"{subject}\". "
                             "(No archived/expired memory found to restore.)"))
            return MemoryCommandResult(
                success=True, operation=operation,
                message=f"Koi active memory nahi mili about \"{subject}\" — kuch badla nahi. "
                        f"(No active memory found for {operation.lower()}; nothing changed.)")

        if len(candidates) > 3:
            lines = "\n".join(f"  {i+1}. {r.content[:80]}" for i, r in enumerate(candidates[:5]))
            return MemoryCommandResult(
                success=True, operation=operation, needs_clarification=True,
                message=("Bahut si matching memories milin. Kaun si apply karoon?\n"
                         + lines + f"\n(Too many matches for {operation.lower()} — which one?)"),
                records=candidates[:5])

        target = max(candidates, key=lambda r: getattr(r, "confidence", 0.0))
        method = getattr(self.manager, operation.lower(), None)
        if method is None:
            return MemoryCommandResult(success=False, operation=operation,
                                       message=f"Unsupported lifecycle op: {operation}")

        if operation == "RESTORE":
            ok = self.manager.restore(target.id)
        elif operation == "BURY":
            ok = self.manager.bury(target.id)
        else:
            ok = method(target.id)

        if not ok:
            current = getattr(target, "status", None)
            return MemoryCommandResult(
                success=False, operation=operation,
                message=(f"Lifecycle op {operation.lower()} failed "
                         f"(current status: {current})."))

        verb = {
            "ARCHIVE": "Archive kar diya",
            "BURY": "Bury kar diya",
            "RETRACT": "Retract kar diya",
            "EXPIRE": "Expire kar diya",
            "RESTORE": "Restore kar diya",
        }[operation]
        return MemoryCommandResult(
            success=True, operation=operation,
            message=f"{verb}: \"{target.content[:60]}\".",
            affected_ids=[target.id], records=[target],
        )

    def _score_query(self, query: str, content: str) -> float:
        tokens = [t for t in query.lower().split() if len(t) > 2]
        if not tokens:
            return 0.0
        content_lower = content.lower()
        return sum(1 for t in tokens if t in content_lower) / len(tokens)

    # ------------------------------------------------------------------
    # FORGET
    # ------------------------------------------------------------------

    def _do_forget(self, command: MemoryCommand, context: Any) -> MemoryCommandResult:
        subject = (command.subject or "").strip()
        if not subject:
            return self._clarify(command)

        candidates = self._find_candidates(subject, limit=10)

        if not candidates:
            return MemoryCommandResult(
                success=True, operation="FORGET",
                message=f"Koi active memory nahi mili about \"{subject}\" — kuch delete nahi kiya. "
                        f"(No active memory found; nothing deleted.)")

        if len(candidates) > 3:
            lines = "\n".join(f"  {i+1}. {r.content[:80]}" for i, r in enumerate(candidates[:5]))
            return MemoryCommandResult(
                success=True, operation="FORGET", needs_clarification=True,
                message=("Bahut si matching memories milin. Kaun si delete karoon?\n"
                         + lines + "\n(Too many matches — which one should I forget?)"),
                records=candidates[:5])

        for record in candidates:
            self.manager.forget(record.id)
        names = ", ".join(f"\"{r.content[:50]}\"" for r in candidates)
        return MemoryCommandResult(
            success=True, operation="FORGET",
            message=f"Forget kar diya: {names}.",
            affected_ids=[r.id for r in candidates], records=candidates,
        )

    # ------------------------------------------------------------------
    # LIST
    # ------------------------------------------------------------------

    def _do_list(self, command: MemoryCommand, context: Any) -> MemoryCommandResult:
        from desktop_agent.brain.memory.unified_model import MemoryScope
        subject = (command.subject or "").strip()
        if subject:
            records = self._find_candidates(subject, limit=15)
        elif command.scope == "PROJECT" and command.project_id:
            records = self.manager.recall_by_scope(MemoryScope.PROJECT,
                                                   project_id=command.project_id, limit=20)
        elif command.scope == "TASK" and command.task_id:
            records = self.manager.recall_by_scope(MemoryScope.TASK,
                                                   task_id=command.task_id, limit=20)
        else:
            records = self.manager.get_all_active()

        if not records:
            return MemoryCommandResult(
                success=True, operation="LIST",
                message="Koi memories nahi milin. (No memories found.)")

        head = f"Memories about \"{subject}\":\n" if subject else "All memories:\n"
        lines = "\n".join(self._format_record(r) for r in records[:20])
        return MemoryCommandResult(
            success=True, operation="LIST",
            message=head + lines,
            records=records[:20], affected_ids=[r.id for r in records[:20]],
        )

    # ------------------------------------------------------------------
    # CLEAR_SCOPE
    # ------------------------------------------------------------------

    def _do_clear_scope(self, command: MemoryCommand, context: Any) -> MemoryCommandResult:
        from desktop_agent.brain.memory.unified_model import MemoryScope

        if command.scope == "PROJECT" and command.project_id:
            records = self.manager.recall_by_scope(MemoryScope.PROJECT,
                                                   project_id=command.project_id, limit=1000)
            for r in records:
                self.manager.forget(r.id)
            return MemoryCommandResult(
                success=True, operation="CLEAR_SCOPE",
                message=(f"Project ki {len(records)} memories saaf kar di. "
                         f"(Cleared {len(records)} project memories.)"),
                affected_ids=[r.id for r in records], records=records)

        if command.scope == "TASK" and command.task_id:
            records = self.manager.recall_by_scope(MemoryScope.TASK,
                                                   task_id=command.task_id, limit=1000)
            for r in records:
                self.manager.forget(r.id)
            return MemoryCommandResult(
                success=True, operation="CLEAR_SCOPE",
                message=(f"Task ki {len(records)} memories saaf kar di. "
                         f"(Cleared {len(records)} task memories.)"),
                affected_ids=[r.id for r in records], records=records)

        return MemoryCommandResult(
            success=False, operation="CLEAR_SCOPE",
            message="Scope context missing — clear karne ke liye project/task batao.")

    # ------------------------------------------------------------------
    # Convenience: full pipeline used by the request flow
    # ------------------------------------------------------------------

    def handle(self, text: str, context: Optional[Any] = None) -> Optional[MemoryCommandResult]:
        """Parse + execute in one call. Returns None when text is not a command."""
        command = self.parser.parse(text, context)
        if not command.is_command:
            return None
        return self.execute(command, context)