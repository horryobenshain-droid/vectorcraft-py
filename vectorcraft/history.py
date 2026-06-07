from __future__ import annotations

from .model import Document


class History:
    def __init__(self, limit: int = 80) -> None:
        self.limit = limit
        self.undo_stack: list[dict] = []
        self.redo_stack: list[dict] = []

    def clear(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()

    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    @property
    def depth(self) -> int:
        return len(self.undo_stack)

    def push(self, document: Document) -> None:
        snapshot = document.to_dict()
        # 连续相同状态去重：避免无变化的空快照占内存、产生空撤销。
        if self.undo_stack and self.undo_stack[-1] == snapshot:
            self.redo_stack.clear()
            return
        self.undo_stack.append(snapshot)
        if len(self.undo_stack) > self.limit:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self, current: Document) -> Document | None:
        if not self.undo_stack:
            return None
        self.redo_stack.append(current.to_dict())
        return Document.from_dict(self.undo_stack.pop())

    def redo(self, current: Document) -> Document | None:
        if not self.redo_stack:
            return None
        self.undo_stack.append(current.to_dict())
        return Document.from_dict(self.redo_stack.pop())
