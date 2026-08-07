"""
File management: create / read / rename / delete / move / open / search.

Safety model:
  * All paths are resolved with expanduser and normalized to absolute.
  * Deletion sends files/folders to the Recycle Bin via `send2trash` when
    available (preferred), and otherwise refuses to delete rather than
    permanently removing data.
  * Operations are confined to a set of SAFE_ROOTS by default; paths that
    escape these roots (e.g. C:\\Windows) are rejected unless explicitly
    marked `allow_anywhere` by the caller.
"""

from __future__ import annotations

import fnmatch
import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .registry import ToolError, register

HOME = Path(os.path.expanduser("~"))

# Roots under which file operations are freely permitted.
SAFE_ROOTS: List[Path] = [
    HOME,
    HOME / "Desktop",
    HOME / "Documents",
    HOME / "Downloads",
    HOME / "Pictures",
    HOME / "Music",
    HOME / "Videos",
    Path(os.getcwd()),  # project root
]

# Friendly folder aliases -> resolved path.
HOME = Path(os.path.expanduser("~"))

# Detect OneDrive folders if available
ONEDRIVE = os.environ.get("OneDrive")

DESKTOP = (
    Path(ONEDRIVE) / "Desktop"
    if ONEDRIVE and (Path(ONEDRIVE) / "Desktop").exists()
    else HOME / "Desktop"
)

DOCUMENTS = (
    Path(ONEDRIVE) / "Documents"
    if ONEDRIVE and (Path(ONEDRIVE) / "Documents").exists()
    else HOME / "Documents"
)

PICTURES = (
    Path(ONEDRIVE) / "Pictures"
    if ONEDRIVE and (Path(ONEDRIVE) / "Pictures").exists()
    else HOME / "Pictures"
)

SAFE_ROOTS: List[Path] = [
    HOME,
    DESKTOP,
    DOCUMENTS,
    HOME / "Downloads",
    PICTURES,
    HOME / "Music",
    HOME / "Videos",
    Path(os.getcwd()),
]

FOLDER_ALIASES: Dict[str, Path] = {
    "desktop": DESKTOP,
    "documents": DOCUMENTS,
    "downloads": HOME / "Downloads",
    "pictures": PICTURES,
    "photos": PICTURES,
    "music": HOME / "Music",
    "videos": HOME / "Videos",
    "home": HOME,
    "this pc": Path("C:\\"),
    "c drive": Path("C:\\"),
}

def _resolve_folder(name_or_path: Optional[str]) -> Path:
    if not name_or_path:
        raise ToolError("Parameter 'name' or 'path' is required.")

    value = str(name_or_path).strip()
    key = value.lower()

    # Known aliases
    if key in FOLDER_ALIASES:
        return FOLDER_ALIASES[key]

    p = Path(os.path.expandvars(os.path.expanduser(value)))

    # Absolute path
    if p.is_absolute():
        return p.resolve()

    # Check inside common folders first
    for base in [
        FOLDER_ALIASES["desktop"],
        FOLDER_ALIASES["documents"],
        FOLDER_ALIASES["downloads"],
        FOLDER_ALIASES["pictures"],
        FOLDER_ALIASES["videos"],
        FOLDER_ALIASES["music"],
        HOME,
    ]:
        candidate = base / value
        if candidate.exists():
            return candidate.resolve()

    # Last fallback
    return p.resolve()


def _resolve_file(path: Optional[str], *, must_exist: bool = False) -> Path:
    if not path:
        raise ToolError("Parameter 'path' is required.")
    p = Path(os.path.expandvars(os.path.expanduser(str(path)))).resolve()
    if must_exist and not p.exists():
        raise ToolError(f"File does not exist: {p}")
    return p


def _ensure_safe(p: Path, allow_anywhere: bool = False) -> None:
    if allow_anywhere:
        return
    real = str(p)
    for root in SAFE_ROOTS:
        try:
            root_real = str(root.resolve())
        except Exception:
            continue
        if real == root_real or real.startswith(root_real + os.sep):
            return
    raise ToolError(
        f"Path '{p}' is outside MYRAA's safe folders (Desktop, Documents, "
        f"Downloads, Pictures, Music, Videos, home, and the project folder). "
        f"Pass allow_anywhere=true only if you really mean it."
    )


@register("createFile")
def create_file(args: Dict[str, Any]) -> Dict[str, Any]:
    path = args.get("path")
    content = args.get("content", "")
    overwrite = bool(args.get("overwrite", False))
    p = _resolve_file(path)
    _ensure_safe(p)

    if p.exists() and not overwrite:
        raise ToolError(
            f"File already exists: {p}. Pass overwrite=true to replace it."
        )
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(content), encoding="utf-8")
    return {"result": f"Created file: {p}", "path": str(p)}


@register("readFile")
def read_file(args: Dict[str, Any]) -> Dict[str, Any]:
    path = args.get("path")
    max_chars = int(args.get("max_chars", 8000))
    p = _resolve_file(path, must_exist=True)
    _ensure_safe(p)
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except UnicodeDecodeError:
        return {"result": f"(Binary file, {p.stat().st_size} bytes): {p}"}
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n…[truncated, {len(text) - max_chars} more chars]"
    return {"result": text, "path": str(p)}


@register("renameFile")
def rename_file(args: Dict[str, Any]) -> Dict[str, Any]:
    path = args.get("path")
    new_name = args.get("new_name")
    if not new_name:
        raise ToolError("Parameter 'new_name' is required.")
    p = _resolve_file(path, must_exist=True)
    _ensure_safe(p)
    target = (p.parent / str(new_name)).resolve()
    _ensure_safe(target)
    if target.exists():
        raise ToolError(f"A file already exists at the target name: {target}")
    p.rename(target)
    return {"result": f"Renamed {p.name} -> {target.name}", "path": str(target)}


@register("deleteFile")
def delete_file(args: Dict[str, Any]) -> Dict[str, Any]:
    path = args.get("path")
    permanent = bool(args.get("permanent", False))
    p = _resolve_file(path, must_exist=True)
    _ensure_safe(p)

    if permanent:
        if p.is_dir():
            import shutil

            shutil.rmtree(p)
        else:
            p.unlink()
        return {"result": f"Permanently deleted: {p}"}

    # Prefer recycle bin.
    try:
        import send2trash  # type: ignore

        send2trash.send2trash(str(p))
        return {"result": f"Moved to Recycle Bin: {p}"}
    except ImportError:
        raise ToolError(
            "Safe deletion requires the 'send2trash' package. Install it or pass "
            "permanent=true (use with care)."
        )
    except Exception as e:  # noqa: BLE001
        raise ToolError(f"Could not move to Recycle Bin: {e}")


@register("moveFile")
def move_file(args: Dict[str, Any]) -> Dict[str, Any]:
    path = args.get("path")
    destination = args.get("destination")
    p = _resolve_file(path, must_exist=True)
    _ensure_safe(p)
    dest = Path(os.path.expandvars(os.path.expanduser(str(destination)))).resolve()
    # If destination is an existing directory, keep the filename.
    if dest.is_dir():
        dest = dest / p.name
    _ensure_safe(dest)
    if dest.exists():
        raise ToolError(f"Destination already exists: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    p.rename(dest)
    return {"result": f"Moved {p.name} -> {dest}", "path": str(dest)}


@register("openFolder")
def open_folder(args: Dict[str, Any]) -> Dict[str, Any]:
    folder = _resolve_folder(args.get("name") or args.get("path"))

    print(f"[openFolder] Resolved folder: {folder}")

    if not folder.exists():
        raise ToolError(f"Folder does not exist: {folder}")
    # Explorer on Windows, open elsewhere.
    if platform.system() == "Windows":
        subprocess.Popen(f'explorer "{folder}"', shell=True, close_fds=True)
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", str(folder)], close_fds=True)
    else:
        subprocess.Popen(["xdg-open", str(folder)], close_fds=True)
    return {"result": f"Opened folder: {folder}", "path": str(folder)}


@register("listFiles")
def list_files(args: Dict[str, Any]) -> Dict[str, Any]:
    folder = _resolve_folder(args.get("name") or args.get("path"))
    if not folder.exists():
        raise ToolError(f"Folder does not exist: {folder}")
    pattern = args.get("pattern") or "*"
    try:
        names = sorted(
            [p.name + ("/" if p.is_dir() else "") for p in folder.glob(pattern)]
        )
    except Exception as e:  # noqa: BLE001
        raise ToolError(f"Could not list folder: {e}")
    return {
        "result": f"{len(names)} item(s) in {folder}",
        "items": names[:500],
        "count": len(names),
    }


@register("searchFiles")
def search_files(args: Dict[str, Any]) -> Dict[str, Any]:
    """Find files by name glob or extension under a folder.

    Examples:
      name="*.py" under "Documents"          -> all python files
      extension="py"                          -> same as name="*.py"
      name="report*" under "Desktop"
    """
    folder = _resolve_folder(args.get("folder") or args.get("under") or "home")
    name = args.get("name") or args.get("pattern")
    extension = args.get("extension")
    limit = int(args.get("limit", 100))

    if extension:
        if not str(extension).startswith("."):
            extension = "." + str(extension)
        pattern = "*" + str(extension)
    elif name:
        pattern = str(name)
    else:
        raise ToolError("Provide 'name' glob or 'extension'.")

    if not folder.exists():
        raise ToolError(f"Folder does not exist: {folder}")

    matches: List[str] = []
    for root, _dirs, files in os.walk(folder):
        for fname in files:
            if fnmatch.fnmatch(fname.lower(), pattern.lower()):
                matches.append(os.path.join(root, fname))
                if len(matches) >= limit:
                    break
        if len(matches) >= limit:
            break

    return {
        "result": f"Found {len(matches)} file(s) matching '{pattern}' under {folder}",
        "matches": matches,
        "count": len(matches),
    }


__all__ = [
    "create_file",
    "read_file",
    "rename_file",
    "delete_file",
    "move_file",
    "open_folder",
    "list_files",
    "search_files",
    "copy_file",
    "open_file",
    "write_file",
]



@register("copyFile")
def copy_file(args: Dict[str, Any]) -> Dict[str, Any]:

    import shutil

    path = args.get("path")
    destination = args.get("destination")

    p = _resolve_file(path, must_exist=True)
    _ensure_safe(p)

    dest = Path(
        os.path.expandvars(
            os.path.expanduser(str(destination))
        )
    ).resolve()

    if dest.is_dir():
        dest = dest / p.name

    _ensure_safe(dest)

    if dest.exists():
        raise ToolError(
            f"Destination already exists: {dest}"
        )

    dest.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    shutil.copy2(
        p,
        dest
    )

    return {
        "result": f"Copied {p.name} -> {dest}",
        "path": str(dest),
    }


@register("openFile")
def open_file(args: Dict[str, Any]) -> Dict[str, Any]:

    path = args.get("path")

    p = _resolve_file(
        path,
        must_exist=True,
    )

    _ensure_safe(p)

    if platform.system() == "Windows":

        os.startfile(p)

    elif platform.system() == "Darwin":

        subprocess.Popen(
            ["open", str(p)]
        )

    else:

        subprocess.Popen(
            ["xdg-open", str(p)]
        )

    return {
        "result": f"Opened {p}",
        "path": str(p),
    }


@register("writeFile")
def write_file(args: Dict[str, Any]) -> Dict[str, Any]:

    path = args.get("path")
    content = args.get("content", "")
    append = bool(
        args.get("append", False)
    )

    p = _resolve_file(path)

    _ensure_safe(p)

    p.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    if append:

        with p.open(
            "a",
            encoding="utf-8"
        ) as f:

            f.write(content)

    else:

        p.write_text(
            str(content),
            encoding="utf-8"
        )

    return {
        "result": f"Written to {p}",
        "path": str(p),
    }