"""Decision tracing: one scheduling pass, told as a tree of spans.

When a pass takes forty ticks nobody can say which filter ate them
without a trace. A span opens with a name, closes with a duration,
and nests: the pass owns a span per task, each task a span per
stage, each stage whatever it wants to note. The tree renders with
durations and the critical path is computed, not eyeballed, walking
the longest child at every level, because the stage worth optimising
is the one on that path and intuition reliably picks a different
one. Spans must close in the order they opened; a span left open is
reported by name at render time instead of corrupting the tree.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid


@dataclass
class Span:
    name: str
    opened_at: int
    closed_at: int | None = None
    notes: list[str] = field(default_factory=list)
    children: list[Span] = field(default_factory=list)

    def duration(self) -> int:
        if self.closed_at is None:
            raise Invalid(f"span {self.name} is still open")
        return self.closed_at - self.opened_at


@dataclass
class Trace:
    root: Span | None = None
    stack: list[Span] = field(default_factory=list)

    def open(self, name: str, now: int) -> Span:
        span = Span(name=name, opened_at=now)
        if self.stack:
            self.stack[-1].children.append(span)
        elif self.root is None:
            self.root = span
        else:
            raise Invalid("a trace has one root; open it before siblings")
        self.stack.append(span)
        return span

    def note(self, text: str) -> None:
        if not self.stack:
            raise Invalid("no open span to note on")
        self.stack[-1].notes.append(text)

    def close(self, name: str, now: int) -> int:
        if not self.stack:
            raise Invalid("nothing is open")
        current = self.stack[-1]
        if current.name != name:
            raise Invalid(
                f"closing {name} but {current.name} is innermost"
            )
        current.closed_at = now
        self.stack.pop()
        return current.duration()

    def still_open(self) -> list[str]:
        return [span.name for span in self.stack]

    def critical_path(self) -> list[str]:
        if self.root is None:
            raise Invalid("an empty trace has no path")
        path = []
        span = self.root
        while span is not None:
            path.append(span.name)
            closed = [
                child for child in span.children if child.closed_at is not None
            ]
            span = (
                max(closed, key=lambda child: (child.duration(), child.name))
                if closed
                else None
            )
        return path

    def render(self) -> str:
        if self.root is None:
            return "empty trace"
        lines: list[str] = []
        self._render_span(self.root, 0, lines)
        for name in self.still_open():
            lines.append(f"WARNING: {name} never closed")
        return "\n".join(lines)

    def _render_span(self, span: Span, depth: int, lines: list[str]) -> None:
        indent = "  " * depth
        if span.closed_at is None:
            lines.append(f"{indent}{span.name} [open]")
        else:
            lines.append(f"{indent}{span.name} ({span.duration()})")
        for note in span.notes:
            lines.append(f"{indent}  - {note}")
        for child in span.children:
            self._render_span(child, depth + 1, lines)
