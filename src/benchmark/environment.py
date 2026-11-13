"""Temporary store data environments for individual benchmark trials."""

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from shutil import copytree
from tempfile import TemporaryDirectory


@contextmanager
def prepare_environment(source_dir: str | Path) -> Generator[Path]:
    """Copy a source directory into a fresh temporary environment.

    Args:
        source_dir: Directory containing the initial store data. Relative paths
            are resolved from the working directory.

    Yields:
        Absolute path to the copied directory, including all nested contents.
        The directory is removed when the context exits, including on errors.

    Raises:
        OSError: The source cannot be copied or the environment cannot be
            created or removed.
    """
    source_path = Path(source_dir).resolve()

    with TemporaryDirectory(prefix="store-benchmark-") as temporary_dir:
        environment_path = Path(temporary_dir).resolve() / "data"
        copytree(source_path, environment_path)
        yield environment_path
