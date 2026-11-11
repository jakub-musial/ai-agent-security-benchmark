from pathlib import Path

from pydantic_ai import ModelRetry, RunContext


def list_documents(ctx: RunContext[Path]) -> list[str]:
    """List available Husarix Markdown document filenames."""
    root = ctx.deps

    return sorted(
        path.name
        for path in root.glob("*.md")
        if path.resolve().is_relative_to(root) and path.is_file()
    )


def read_document(ctx: RunContext[Path], name: str) -> str:
    """Read the full text of a Husarix Markdown document.

    Args:
        name: Exact filename returned by list_documents.
    """
    root = ctx.deps
    documents = {path.name: path for path in root.glob("*.md")}
    document = documents.get(name)

    if document is None:
        raise ModelRetry("Unknown document. Use list_documents.")

    path = document.resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ModelRetry("This document is unavailable.")

    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ModelRetry("The document could not be read.") from exc
