#!/usr/bin/env python3
"""Hash and archive the exact Python source tree Ansible will deploy."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import os
from pathlib import Path
import tarfile
import tempfile


def source_files(repository: Path) -> list[Path]:
    required = [repository / "README.md", repository / "pyproject.toml"]
    source_root = repository / "src"
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise SystemExit("missing deployable source: {}".format(missing[0]))
    if not source_root.is_dir():
        raise SystemExit("missing deployable source directory: {}".format(source_root))

    files = list(required)
    files.extend(
        path
        for path in source_root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    )
    return sorted(files, key=lambda path: path.relative_to(repository).as_posix())


def read_source(files: list[Path]) -> list[tuple[Path, bytes]]:
    return [(path, path.read_bytes()) for path in files]


def content_revision(repository: Path, source: list[tuple[Path, bytes]]) -> str:
    digest = hashlib.sha256()
    for path, content in source:
        relative = path.relative_to(repository).as_posix().encode()
        digest.update(relative)
        digest.update(b"\0")
        digest.update(str(len(content)).encode())
        digest.update(b"\0")
        digest.update(content)
    return "sha256-{}".format(digest.hexdigest())


def write_archive(
    repository: Path,
    source: list[tuple[Path, bytes]],
    output: Path,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output.parent,
        prefix=".{}-".format(output.name),
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with temporary.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
                with tarfile.open(fileobj=zipped, mode="w") as archive:
                    for path, content in source:
                        relative = path.relative_to(repository).as_posix()
                        info = tarfile.TarInfo("app/{}".format(relative))
                        info.size = len(content)
                        info.mode = 0o644
                        info.mtime = 0
                        info.uid = 0
                        info.gid = 0
                        info.uname = ""
                        info.gname = ""
                        archive.addfile(info, io.BytesIO(content))
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("repository", type=Path)
    parser.add_argument("--print-revision", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expect-revision")
    args = parser.parse_args()

    repository = args.repository.resolve()
    files = source_files(repository)
    source = read_source(files)
    revision = content_revision(repository, source)
    if args.expect_revision and args.expect_revision != revision:
        raise SystemExit(
            "source changed during packaging: expected {}, found {}".format(
                args.expect_revision,
                revision,
            )
        )
    if args.output:
        write_archive(repository, source, args.output.resolve())
    if args.print_revision or not args.output:
        print(revision)


if __name__ == "__main__":
    main()
