"""
Entity definitions stored inside Working Memory.
"""

from dataclasses import dataclass


@dataclass(slots=True)
class ApplicationEntity:
    name: str


@dataclass(slots=True)
class WebsiteEntity:
    url: str


@dataclass(slots=True)
class FileEntity:
    path: str


@dataclass(slots=True)
class FolderEntity:
    path: str


@dataclass(slots=True)
class PersonEntity:
    name: str