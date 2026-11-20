"""Temporary store data environments for individual benchmark trials."""

import sqlite3
from collections.abc import Generator
from contextlib import closing, contextmanager
from pathlib import Path
from shutil import copytree
from tempfile import TemporaryDirectory

STORE_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "store.sql"


@contextmanager
def prepare_environment(source_dir: str | Path) -> Generator[Path]:
    """Copy store documents and initialize a fresh SQLite database for a trial.

    Args:
        source_dir: Directory containing the initial store data. Relative paths
            are resolved from the working directory.

    Yields:
        Absolute path to the copied directory containing the documents and
        store.sqlite3.
        The directory is removed when the context exits, including on errors.

    Raises:
        OSError: The source cannot be copied or the environment cannot be
            created or removed, or the SQL fixture cannot be read.
        sqlite3.Error: The store database cannot be initialized.
    """
    source_path = Path(source_dir).resolve()

    with TemporaryDirectory(prefix="store-benchmark-") as temporary_dir:
        environment_path = Path(temporary_dir).resolve() / "data"
        copytree(source_path, environment_path)
        store_sql = STORE_FIXTURE.read_text(encoding="utf-8")
        with closing(sqlite3.connect(environment_path / "store.sqlite3")) as database:
            database.executescript(store_sql)
        yield environment_path
