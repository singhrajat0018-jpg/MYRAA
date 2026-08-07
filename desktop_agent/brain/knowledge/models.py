"""
MYRAA Knowledge Engine
Core data models shared across scanners, indexers and search.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List


# ---------------------------------------------------------
# File Metadata
# ---------------------------------------------------------

@dataclass(slots=True)
class FileMetadata:

    path: str
    name: str
    extension: str

    size: int

    created_at: datetime
    modified_at: datetime

    parent: str

    tags: List[str] = field(default_factory=list)

    indexed: bool = False


# ---------------------------------------------------------
# Application Metadata
# ---------------------------------------------------------

@dataclass(slots=True)
class ApplicationMetadata:

    name: str

    executable: str

    install_path: str

    publisher: str = ""

    version: str = ""


# ---------------------------------------------------------
# Folder Metadata
# ---------------------------------------------------------

@dataclass(slots=True)
class FolderMetadata:

    path: str

    name: str

    parent: str

    file_count: int = 0

    folder_count: int = 0


# ---------------------------------------------------------
# Search Result
# ---------------------------------------------------------

@dataclass(slots=True)
class SearchResult:

    score: float

    path: str

    title: str

    metadata: Dict = field(default_factory=dict)


# ---------------------------------------------------------
# Project Metadata
# ---------------------------------------------------------

@dataclass(slots=True)
class ProjectMetadata:

    root: str

    name: str

    languages: List[str] = field(default_factory=list)

    frameworks: List[str] = field(default_factory=list)

    files: int = 0

    folders: int = 0