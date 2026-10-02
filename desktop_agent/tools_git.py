"""
Git tools for project building.

Provides Git operations with:
- Repository status
- Diff viewing
- Log/history
- Staging/committing
- Push/pull
- Branch management
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .registry import ToolError, register


def _resolve_repo_path(path: Optional[str]) -> Path:
    """Resolve repository path, defaulting to current directory."""
    if not path:
        return Path.cwd()
    p = Path(os.path.expandvars(os.path.expanduser(str(path)))).resolve()
    return p


def _run_git(args: List[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    cmd = ["git"] + args
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
    )


def _check_git_repo(cwd: Path) -> None:
    """Verify we're in a git repository."""
    result = _run_git(["rev-parse", "--git-dir"], cwd)
    if result.returncode != 0:
        raise ToolError(f"Not a git repository: {cwd}")


@register("gitStatus")
def git_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get git repository status.
    
    Args:
        path: Repository path (optional, defaults to cwd)
        
    Returns:
        Dict with status info
    """
    cwd = _resolve_repo_path(args.get("path"))
    _check_git_repo(cwd)
    
    # Get status
    result = _run_git(["status", "--porcelain", "-b"], cwd)
    if result.returncode != 0:
        raise ToolError(f"git status failed: {result.stderr}")
    
    lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
    
    # Parse branch info from first line
    branch_info = lines[0] if lines else ""
    branch = branch_info.replace("## ", "").split("...")[0] if branch_info.startswith("##") else ""
    
    # Parse file statuses
    staged = []
    unstaged = []
    untracked = []
    
    for line in lines[1:]:
        if not line:
            continue
        status = line[:2]
        filepath = line[3:]
        if status[0] != " " and status[0] != "?":
            staged.append({"file": filepath, "status": status[0]})
        if status[1] != " ":
            unstaged.append({"file": filepath, "status": status[1]})
        if status == "??":
            untracked.append(filepath)
    
    return {
        "ok": True,
        "branch": branch,
        "staged": staged,
        "unstaged": unstaged,
        "untracked": untracked,
        "clean": len(staged) == 0 and len(unstaged) == 0 and len(untracked) == 0,
    }


@register("gitDiff")
def git_diff(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get git diff.
    
    Args:
        path: Repository path
        staged: Whether to show staged changes (default: False)
        file: Specific file to diff (optional)
        
    Returns:
        Dict with diff output
    """
    cwd = _resolve_repo_path(args.get("path"))
    _check_git_repo(cwd)
    
    staged = bool(args.get("staged", False))
    file_path = args.get("file")
    
    args_list = ["diff"]
    if staged:
        args_list.append("--staged")
    if file_path:
        args_list.append("--")
        args_list.append(file_path)
    
    result = _run_git(args_list, cwd)
    if result.returncode != 0:
        raise ToolError(f"git diff failed: {result.stderr}")
    
    diff = result.stdout
    if len(diff) > 20000:
        diff = diff[:20000] + "\n...[truncated]"
    
    return {
        "ok": True,
        "diff": diff,
        "staged": staged,
    }


@register("gitLog")
def git_log(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get git commit log.
    
    Args:
        path: Repository path
        limit: Number of commits (default: 20)
        oneline: Use oneline format (default: True)
        file: Filter by file (optional)
        
    Returns:
        Dict with commit list
    """
    cwd = _resolve_repo_path(args.get("path"))
    _check_git_repo(cwd)
    
    limit = int(args.get("limit", 20))
    oneline = bool(args.get("oneline", True))
    file_path = args.get("file")
    
    args_list = ["log"]
    if oneline:
        args_list.append("--oneline")
    else:
        args_list.append("--pretty=format:%H|%an|%ad|%s")
        args_list.append("--date=short")
    args_list.append(f"-n{limit}")
    if file_path:
        args_list.append("--")
        args_list.append(file_path)
    
    result = _run_git(args_list, cwd)
    if result.returncode != 0:
        raise ToolError(f"git log failed: {result.stderr}")
    
    lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
    commits = []
    for line in lines:
        if not line:
            continue
        if oneline:
            parts = line.split(" ", 1)
            commits.append({"hash": parts[0], "message": parts[1] if len(parts) > 1 else ""})
        else:
            parts = line.split("|", 3)
            if len(parts) >= 4:
                commits.append({"hash": parts[0], "author": parts[1], "date": parts[2], "message": parts[3]})
    
    return {
        "ok": True,
        "commits": commits,
    }


@register("gitAdd")
def git_add(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stage files for commit.
    
    Args:
        path: Repository path
        files: List of files to stage, or "all" for all changes
        
    Returns:
        Dict with result
    """
    cwd = _resolve_repo_path(args.get("path"))
    _check_git_repo(cwd)
    
    files = args.get("files", "all")
    if files == "all":
        files_list = ["."]
    elif isinstance(files, str):
        files_list = [files]
    elif isinstance(files, list):
        files_list = files
    else:
        raise ToolError("Parameter 'files' must be a string or list")
    
    result = _run_git(["add"] + files_list, cwd)
    if result.returncode != 0:
        raise ToolError(f"git add failed: {result.stderr}")
    
    return {"ok": True, "message": f"Staged: {files_list}"}


@register("gitCommit")
def git_commit(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a commit.
    
    Args:
        path: Repository path
        message: Commit message
        author: Author string (optional)
        
    Returns:
        Dict with commit info
    """
    cwd = _resolve_repo_path(args.get("path"))
    _check_git_repo(cwd)
    
    message = args.get("message")
    if not message:
        raise ToolError("Parameter 'message' is required.")
    
    author = args.get("author")
    args_list = ["commit", "-m", message]
    if author:
        args_list.extend(["--author", author])
    
    result = _run_git(args_list, cwd)
    if result.returncode != 0:
        raise ToolError(f"git commit failed: {result.stderr}")
    
    return {"ok": True, "message": "Committed", "output": result.stdout}


@register("gitPush")
def git_push(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Push commits to remote.
    
    Args:
        path: Repository path
        remote: Remote name (default: origin)
        branch: Branch name (optional, defaults to current)
        
    Returns:
        Dict with result
    """
    cwd = _resolve_repo_path(args.get("path"))
    _check_git_repo(cwd)
    
    remote = args.get("remote", "origin")
    branch = args.get("branch")
    
    args_list = ["push", remote]
    if branch:
        args_list.append(branch)
    
    result = _run_git(args_list, cwd)
    if result.returncode != 0:
        raise ToolError(f"git push failed: {result.stderr}")
    
    return {"ok": True, "output": result.stdout}


@register("gitPull")
def git_pull(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pull changes from remote.
    
    Args:
        path: Repository path
        remote: Remote name (default: origin)
        branch: Branch name (optional)
        
    Returns:
        Dict with result
    """
    cwd = _resolve_repo_path(args.get("path"))
    _check_git_repo(cwd)
    
    remote = args.get("remote", "origin")
    branch = args.get("branch")
    
    args_list = ["pull", remote]
    if branch:
        args_list.append(branch)
    
    result = _run_git(args_list, cwd)
    if result.returncode != 0:
        raise ToolError(f"git pull failed: {result.stderr}")
    
    return {"ok": True, "output": result.stdout}


@register("gitBranch")
def git_branch(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    List or create branches.
    
    Args:
        path: Repository path
        create: New branch name to create (optional)
        delete: Branch name to delete (optional)
        
    Returns:
        Dict with branch list or result
    """
    cwd = _resolve_repo_path(args.get("path"))
    _check_git_repo(cwd)
    
    create = args.get("create")
    delete = args.get("delete")
    
    if create:
        result = _run_git(["checkout", "-b", create], cwd)
        if result.returncode != 0:
            raise ToolError(f"git branch create failed: {result.stderr}")
        return {"ok": True, "message": f"Created branch: {create}", "output": result.stdout}
    
    if delete:
        result = _run_git(["branch", "-d", delete], cwd)
        if result.returncode != 0:
            raise ToolError(f"git branch delete failed: {result.stderr}")
        return {"ok": True, "message": f"Deleted branch: {delete}", "output": result.stdout}
    
    # List branches
    result = _run_git(["branch", "-a"], cwd)
    if result.returncode != 0:
        raise ToolError(f"git branch failed: {result.stderr}")
    
    branches = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        current = line.startswith("*")
        name = line.replace("* ", "").replace("remotes/", "").strip()
        branches.append({"name": name, "current": current})
    
    return {"ok": True, "branches": branches}


@register("gitCheckout")
def git_checkout(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Switch branches or restore files.
    
    Args:
        path: Repository path
        branch: Branch name to checkout
        create: Create new branch (bool)
        file: File to restore (optional)
        
    Returns:
        Dict with result
    """
    cwd = _resolve_repo_path(args.get("path"))
    _check_git_repo(cwd)
    
    branch = args.get("branch")
    create = bool(args.get("create", False))
    file_path = args.get("file")
    
    if file_path:
        result = _run_git(["checkout", "--", file_path], cwd)
    elif create and branch:
        result = _run_git(["checkout", "-b", branch], cwd)
    elif branch:
        result = _run_git(["checkout", branch], cwd)
    else:
        raise ToolError("Either 'branch' or 'file' parameter is required.")
    
    if result.returncode != 0:
        raise ToolError(f"git checkout failed: {result.stderr}")
    
    return {"ok": True, "output": result.stdout}


__all__ = [
    "git_status", "git_diff", "git_log", "git_add", 
    "git_commit", "git_push", "git_pull", "git_branch", "git_checkout",
]