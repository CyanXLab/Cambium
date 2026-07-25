from __future__ import annotations
"""
Extended tool definitions and implementations for the AI Chat agent.

This module provides:
- Comprehensive file operations (read, write, edit, str_replace, regex, patch,
  multi-edit, append, prepend, line ops, move, copy, stat, mkdir, tree)
- Search tools (grep, glob, find)
- Web tools (web_search via MCP, web_fetch)
- Skill self-evolution tools (skill_create, skill_update, skill_read, tool_save)
- Session tools (sessions_list, sessions_history, session_status, sessions_send,
  sessions_spawn)
- Workflow tools (todo_write, plan_write, finish)
- Memory tools (memory_search, memory_add, memory_update)

All tools operate on a workspace directory and are sandboxed.
"""
import os
import re
import sys
from app.db_utils import safe_connect
import json
import time
import shutil
import hashlib
import asyncio
import difflib
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta


# ============================================================
# Path resolution & sandbox enforcement
# ============================================================
def _safe_resolve(workspace: Path, path: str) -> Path:
    """Resolve path relative to workspace and ensure it stays within sandbox.
    Allows paths within workspace; rejects paths that escape via ../."""
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = workspace / path
    try:
        # Resolve and check containment
        resolved = p.resolve() if p.exists() else p.absolute()
        ws_resolved = workspace.resolve()
        # Allow if resolved path is within workspace
        try:
            resolved.relative_to(ws_resolved)
            return resolved
        except ValueError:
            pass
        # Also allow if absolute path was explicitly given AND it's a known safe dir
        # (e.g., user's home for read-only operations). For safety we restrict to workspace.
        raise PermissionError(f"Path '{path}' is outside workspace sandbox")
    except Exception:
        raise PermissionError(f"Cannot resolve path '{path}'")


def _check_workspace(workspace: Path):
    workspace.mkdir(parents=True, exist_ok=True)


# ============================================================
# File operations
# ============================================================

def tool_read_file(workspace: Path, args: Dict) -> Dict:
    """Read file with optional line range."""
    _check_workspace(workspace)
    path = args.get("path", "")
    if not path:
        return {"success": False, "error": "path required"}
    offset = int(args.get("offset", 0) or 0)
    limit = int(args.get("limit", 0) or 0)
    try:
        fp = _safe_resolve(workspace, path)
        if not fp.exists():
            return {"success": False, "error": f"file not found: {path}"}
        if not fp.is_file():
            return {"success": False, "error": f"not a file: {path}"}
        content = fp.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")
        total = len(lines)
        if offset > 0 or limit > 0:
            start = offset if offset > 0 else 0
            end = start + limit if limit > 0 else total
            lines = lines[start:end]
            shown = "\n".join(lines)
            return {
                "success": True,
                "result": shown,
                "path": str(fp),
                "total_lines": total,
                "shown_range": [start, end],
            }
        if len(content) > 50000:
            content = content[:50000] + f"\n...[truncated, {len(content)-50000} more chars]"
        return {"success": True, "result": content, "path": str(fp), "total_lines": total}
    except PermissionError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_write_file(workspace: Path, args: Dict) -> Dict:
    """Write content to file. Default overwrites; set append=true to append."""
    _check_workspace(workspace)
    path = args.get("path", "")
    content = args.get("content", "")
    append = bool(args.get("append", False))
    if not path:
        return {"success": False, "error": "path required"}
    try:
        fp = _safe_resolve(workspace, path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        if append and fp.exists():
            old = fp.read_text(encoding="utf-8", errors="replace")
            content = old + content
        fp.write_text(content, encoding="utf-8")
        return {
            "success": True,
            "result": f"wrote {len(content)} chars to {path}",
            "path": str(fp),
            "bytes": len(content.encode("utf-8")),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_str_replace(workspace: Path, args: Dict) -> Dict:
    """Replace first occurrence of old_str with new_str in a file.
    Set replace_all=true to replace all occurrences."""
    _check_workspace(workspace)
    path = args.get("path", "")
    old_str = args.get("old_str", "")
    new_str = args.get("new_str", "")
    replace_all = bool(args.get("replace_all", False))
    if not path or not old_str:
        return {"success": False, "error": "path and old_str required"}
    try:
        fp = _safe_resolve(workspace, path)
        if not fp.exists():
            return {"success": False, "error": f"file not found: {path}"}
        content = fp.read_text(encoding="utf-8", errors="replace")
        count = content.count(old_str)
        if count == 0:
            return {
                "success": False,
                "error": f"old_str not found in {path}. Use read_file to verify content.",
                "hint": "The string must match EXACTLY (including whitespace).",
            }
        if replace_all:
            new_content = content.replace(old_str, new_str)
            replaced = count
        else:
            # Verify uniqueness when not replace_all
            if count > 1:
                # Add line context to help locate
                line_starts = []
                for i, line in enumerate(content.split("\n"), 1):
                    if old_str in line:
                        line_starts.append(i)
                return {
                    "success": False,
                    "error": f"old_str found {count} times in {path} (lines: {line_starts[:5]}). Set replace_all=true or include more context to make it unique.",
                }
            new_content = content.replace(old_str, new_str, 1)
            replaced = 1
        fp.write_text(new_content, encoding="utf-8")
        # Compute unified diff snippet
        diff = "\n".join(difflib.unified_diff(
            content.splitlines(keepends=True)[:50],
            new_content.splitlines(keepends=True)[:50],
            fromfile=f"{path} (before)",
            tofile=f"{path} (after)",
            n=2,
        ))[:1500]
        return {
            "success": True,
            "result": f"replaced {replaced} occurrence(s) in {path}",
            "replaced": replaced,
            "diff": diff,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_regex_replace(workspace: Path, args: Dict) -> Dict:
    """Replace text matching a regex pattern in a file."""
    _check_workspace(workspace)
    path = args.get("path", "")
    pattern = args.get("pattern", "")
    replacement = args.get("replacement", "")
    flags_str = args.get("flags", "g")  # g, i, m, s
    if not path or not pattern:
        return {"success": False, "error": "path and pattern required"}
    try:
        fp = _safe_resolve(workspace, path)
        if not fp.exists():
            return {"success": False, "error": f"file not found: {path}"}
        content = fp.read_text(encoding="utf-8", errors="replace")
        flags = 0
        if "i" in flags_str: flags |= re.IGNORECASE
        if "m" in flags_str: flags |= re.MULTILINE
        if "s" in flags_str: flags |= re.DOTALL
        count = 0 if "g" in flags_str else 1
        new_content, n = re.subn(pattern, replacement, content, count=count, flags=flags)
        if n == 0:
            return {"success": False, "error": f"pattern not matched in {path}"}
        fp.write_text(new_content, encoding="utf-8")
        return {
            "success": True,
            "result": f"replaced {n} match(es) in {path}",
            "replaced": n,
        }
    except re.error as e:
        return {"success": False, "error": f"invalid regex: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_multi_edit(workspace: Path, args: Dict) -> Dict:
    """Apply multiple edits to a single file in one call.
    Each edit is applied in sequence; if any fails, none are applied (transactional)."""
    _check_workspace(workspace)
    path = args.get("path", "")
    edits = args.get("edits", [])
    if not path or not edits:
        return {"success": False, "error": "path and edits required"}
    try:
        fp = _safe_resolve(workspace, path)
        if not fp.exists():
            return {"success": False, "error": f"file not found: {path}"}
        content = fp.read_text(encoding="utf-8", errors="replace")
        original = content
        applied = 0
        for i, edit in enumerate(edits):
            old_str = edit.get("old_str", "")
            new_str = edit.get("new_str", "")
            if not old_str:
                return {"success": False, "error": f"edit #{i}: old_str required"}
            if old_str not in content:
                # Rollback
                fp.write_text(original, encoding="utf-8")
                return {"success": False, "error": f"edit #{i}: old_str not found (rolled back all edits)"}
            content = content.replace(old_str, new_str, 1)
            applied += 1
        fp.write_text(content, encoding="utf-8")
        return {
            "success": True,
            "result": f"applied {applied} edits to {path}",
            "applied": applied,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_apply_patch(workspace: Path, args: Dict) -> Dict:
    """Apply a unified diff patch to a file. Supports standard unified diff format."""
    _check_workspace(workspace)
    path = args.get("path", "")
    patch = args.get("patch", "")
    if not path or not patch:
        return {"success": False, "error": "path and patch required"}
    try:
        fp = _safe_resolve(workspace, path)
        if not fp.exists():
            return {"success": False, "error": f"file not found: {path}"}
        original = fp.read_text(encoding="utf-8", errors="replace")
        # Apply patch line by line
        original_lines = original.splitlines(keepends=True)
        patch_lines = patch.splitlines()
        result_lines = []
        i = 0
        pi = 0
        # Skip patch header (--- and +++ lines)
        while pi < len(patch_lines) and not patch_lines[pi].startswith("@@"):
            pi += 1
        while pi < len(patch_lines):
            line = patch_lines[pi]
            if line.startswith("@@"):
                # Parse hunk header: @@ -start,count +start,count @@
                m = re.match(r"^@@ -(\d+),?\d* \+(\d+),?\d* @@", line)
                if not m:
                    pi += 1
                    continue
                old_start = int(m.group(1))
                # Skip to that line in original (1-indexed)
                while i < old_start - 1 and i < len(original_lines):
                    result_lines.append(original_lines[i])
                    i += 1
                pi += 1
                # Process hunk body
                while pi < len(patch_lines) and not patch_lines[pi].startswith("@@"):
                    pl = patch_lines[pi]
                    if pl.startswith("-"):
                        # Removed line: skip in original
                        i += 1
                    elif pl.startswith("+"):
                        # Added line
                        result_lines.append(pl[1:] + "\n")
                    elif pl.startswith(" "):
                        # Context line
                        if i < len(original_lines):
                            result_lines.append(original_lines[i])
                        i += 1
                    elif pl.startswith("\\"):
                        # No newline at end of file marker
                        pass
                    pi += 1
            else:
                pi += 1
        # Append remaining original lines
        while i < len(original_lines):
            result_lines.append(original_lines[i])
            i += 1
        new_content = "".join(result_lines)
        fp.write_text(new_content, encoding="utf-8")
        return {
            "success": True,
            "result": f"patch applied to {path}",
            "original_size": len(original),
            "new_size": len(new_content),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_file_append(workspace: Path, args: Dict) -> Dict:
    """Append text to a file (creates if not exists)."""
    args["append"] = True
    return tool_write_file(workspace, args)


def tool_file_prepend(workspace: Path, args: Dict) -> Dict:
    """Prepend text to a file (creates if not exists)."""
    _check_workspace(workspace)
    path = args.get("path", "")
    content = args.get("content", "")
    if not path:
        return {"success": False, "error": "path required"}
    try:
        fp = _safe_resolve(workspace, path)
        old = ""
        if fp.exists():
            old = fp.read_text(encoding="utf-8", errors="replace")
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content + old, encoding="utf-8")
        return {"success": True, "result": f"prepended {len(content)} chars to {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_insert_lines(workspace: Path, args: Dict) -> Dict:
    """Insert lines at a specific line number (1-indexed)."""
    _check_workspace(workspace)
    path = args.get("path", "")
    line_num = int(args.get("line", 1))
    content = args.get("content", "")
    if not path:
        return {"success": False, "error": "path required"}
    try:
        fp = _safe_resolve(workspace, path)
        if not fp.exists():
            return {"success": False, "error": f"file not found: {path}"}
        old = fp.read_text(encoding="utf-8", errors="replace")
        lines = old.split("\n")
        # line_num is 1-indexed
        idx = max(0, min(line_num - 1, len(lines)))
        new_lines = content.split("\n")
        lines[idx:idx] = new_lines
        new_content = "\n".join(lines)
        fp.write_text(new_content, encoding="utf-8")
        return {"success": True, "result": f"inserted {len(new_lines)} lines at line {line_num}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_delete_lines(workspace: Path, args: Dict) -> Dict:
    """Delete a range of lines (1-indexed, inclusive)."""
    _check_workspace(workspace)
    path = args.get("path", "")
    start = int(args.get("start", 1))
    end = int(args.get("end", start))
    if not path:
        return {"success": False, "error": "path required"}
    try:
        fp = _safe_resolve(workspace, path)
        if not fp.exists():
            return {"success": False, "error": f"file not found: {path}"}
        old = fp.read_text(encoding="utf-8", errors="replace")
        lines = old.split("\n")
        # 1-indexed inclusive
        s = max(0, start - 1)
        e = min(len(lines), end)
        deleted = lines[s:e]
        del lines[s:e]
        new_content = "\n".join(lines)
        fp.write_text(new_content, encoding="utf-8")
        return {
            "success": True,
            "result": f"deleted {len(deleted)} lines ({start}-{end}) from {path}",
            "deleted_content": "\n".join(deleted)[:1000],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_file_move(workspace: Path, args: Dict) -> Dict:
    """Move or rename a file/directory."""
    _check_workspace(workspace)
    src = args.get("source", "")
    dst = args.get("destination", "")
    if not src or not dst:
        return {"success": False, "error": "source and destination required"}
    try:
        sp = _safe_resolve(workspace, src)
        dp = _safe_resolve(workspace, dst)
        if not sp.exists():
            return {"success": False, "error": f"source not found: {src}"}
        dp.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(sp), str(dp))
        return {"success": True, "result": f"moved {src} → {dst}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_file_copy(workspace: Path, args: Dict) -> Dict:
    """Copy a file or directory."""
    _check_workspace(workspace)
    src = args.get("source", "")
    dst = args.get("destination", "")
    if not src or not dst:
        return {"success": False, "error": "source and destination required"}
    try:
        sp = _safe_resolve(workspace, src)
        dp = _safe_resolve(workspace, dst)
        if not sp.exists():
            return {"success": False, "error": f"source not found: {src}"}
        dp.parent.mkdir(parents=True, exist_ok=True)
        if sp.is_dir():
            shutil.copytree(str(sp), str(dp))
        else:
            shutil.copy2(str(sp), str(dp))
        return {"success": True, "result": f"copied {src} → {dst}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_delete_file(workspace: Path, args: Dict) -> Dict:
    """Delete a file or directory."""
    _check_workspace(workspace)
    path = args.get("path", "")
    recursive = bool(args.get("recursive", False))
    if not path:
        return {"success": False, "error": "path required"}
    # Safety: block any path containing '..' that would escape workspace
    try:
        fp = _safe_resolve(workspace, path)
        if not fp.exists():
            return {"success": False, "error": f"path not found: {path}"}
        if fp.is_dir():
            if not recursive:
                return {"success": False, "error": "is a directory; set recursive=true to delete"}
            shutil.rmtree(str(fp))
        else:
            fp.unlink()
        return {"success": True, "result": f"deleted {path}"}
    except PermissionError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_make_directory(workspace: Path, args: Dict) -> Dict:
    """Create a directory (and parents)."""
    _check_workspace(workspace)
    path = args.get("path", "")
    if not path:
        return {"success": False, "error": "path required"}
    try:
        fp = _safe_resolve(workspace, path)
        fp.mkdir(parents=True, exist_ok=True)
        return {"success": True, "result": f"created directory {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_file_stat(workspace: Path, args: Dict) -> Dict:
    """Get file/directory metadata: size, mtime, mode, etc."""
    _check_workspace(workspace)
    path = args.get("path", "")
    if not path:
        return {"success": False, "error": "path required"}
    try:
        fp = _safe_resolve(workspace, path)
        if not fp.exists():
            return {"success": False, "error": f"path not found: {path}"}
        st = fp.stat()
        return {
            "success": True,
            "result": {
                "path": str(fp),
                "size": st.st_size,
                "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(),
                "ctime": datetime.fromtimestamp(st.st_ctime).isoformat(),
                "mode": oct(st.st_mode & 0o777),
                "is_dir": fp.is_dir(),
                "is_file": fp.is_file(),
                "is_symlink": fp.is_symlink(),
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_file_tree(workspace: Path, args: Dict) -> Dict:
    """List files recursively as a tree, with optional path/glob filter."""
    _check_workspace(workspace)
    path = args.get("path", ".")
    max_depth = int(args.get("max_depth", 3))
    include_pattern = args.get("include", "")  # glob pattern
    try:
        fp = _safe_resolve(workspace, path)
        if not fp.exists():
            return {"success": False, "error": f"path not found: {path}"}
        if not fp.is_dir():
            return {"success": False, "error": f"not a directory: {path}"}
        items = []
        for root, dirs, files in os.walk(str(fp)):
            # Compute depth
            rel = os.path.relpath(root, str(fp))
            depth = 0 if rel == "." else rel.count(os.sep) + 1
            if depth >= max_depth:
                dirs.clear()  # don't descend further
                continue
            for f in files:
                full = os.path.join(root, f)
                rel_path = os.path.relpath(full, str(fp))
                if include_pattern:
                    from fnmatch import fnmatch
                    if not fnmatch(f, include_pattern):
                        continue
                try:
                    size = os.path.getsize(full)
                except OSError:
                    size = 0
                items.append({"path": rel_path, "size": size, "depth": depth})
            for d in dirs:
                full = os.path.join(root, d)
                rel_path = os.path.relpath(full, str(fp))
                items.append({"path": rel_path + "/", "type": "dir", "depth": depth})
        # Limit output
        if len(items) > 500:
            items = items[:500]
        return {
            "success": True,
            "result": items,
            "total": len(items),
            "truncated": len(items) >= 500,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# Search tools
# ============================================================

def tool_grep(workspace: Path, args: Dict) -> Dict:
    """Search file contents with regex (like ripgrep). Returns matching lines with file:line:content."""
    _check_workspace(workspace)
    pattern = args.get("pattern", "")
    path = args.get("path", ".")
    case_insensitive = bool(args.get("case_insensitive", False))
    include_pattern = args.get("include", "")  # glob like "*.py"
    max_results = int(args.get("max_results", 100))
    if not pattern:
        return {"success": False, "error": "pattern required"}
    try:
        fp = _safe_resolve(workspace, path)
        if not fp.exists():
            return {"success": False, "error": f"path not found: {path}"}
        flags = re.IGNORECASE if case_insensitive else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return {"success": False, "error": f"invalid regex: {e}"}
        matches = []
        from fnmatch import fnmatch
        # Walk
        if fp.is_file():
            files_to_search = [fp]
        else:
            files_to_search = []
            for root, dirs, files in os.walk(str(fp)):
                # Skip hidden dirs and __pycache__
                dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
                for f in files:
                    if include_pattern and not fnmatch(f, include_pattern):
                        continue
                    files_to_search.append(Path(root) / f)
                    if len(files_to_search) > 1000:
                        break
                if len(files_to_search) > 1000:
                    break
        for fpath in files_to_search:
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    for line_num, line in enumerate(f, 1):
                        if regex.search(line):
                            rel = os.path.relpath(str(fpath), str(workspace))
                            matches.append({
                                "file": rel,
                                "line": line_num,
                                "content": line.rstrip("\n")[:300],
                            })
                            if len(matches) >= max_results:
                                return {
                                    "success": True,
                                    "result": matches,
                                    "total": len(matches),
                                    "truncated": True,
                                }
            except Exception:
                continue
        return {"success": True, "result": matches, "total": len(matches)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_glob(workspace: Path, args: Dict) -> Dict:
    """Find files matching a glob pattern (e.g., '**/*.py')."""
    _check_workspace(workspace)
    pattern = args.get("pattern", "**/*")
    path = args.get("path", ".")
    try:
        fp = _safe_resolve(workspace, path)
        if not fp.exists():
            return {"success": False, "error": f"path not found: {path}"}
        # Use pathlib glob
        if fp.is_file():
            return {"success": True, "result": [str(fp)], "total": 1}
        results = []
        for p in fp.glob(pattern):
            try:
                rel = p.relative_to(workspace)
                results.append(str(rel))
            except ValueError:
                results.append(str(p))
            if len(results) >= 500:
                break
        return {"success": True, "result": sorted(results), "total": len(results)}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# Web tools (web_fetch is in-process; web_search delegates to MCP)
# ============================================================

def tool_web_fetch(workspace: Path, args: Dict) -> Dict:
    """Fetch the content of a URL and return as text. Strips HTML to text.
    For simple page reads — not for JS-rendered content."""
    import urllib.request, urllib.parse, urllib.error
    url = args.get("url", "")
    raw = bool(args.get("raw_html", False))
    max_chars = int(args.get("max_chars", 20000))
    if not url:
        return {"success": False, "error": "url required"}
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read()
            # Detect encoding
            charset = "utf-8"
            if "charset=" in content_type:
                charset = content_type.split("charset=")[-1].split(";")[0].strip()
            try:
                text = data.decode(charset, errors="replace")
            except LookupError:
                text = data.decode("utf-8", errors="replace")
            if not raw and "html" in content_type.lower():
                # Simple HTML to text
                text = _html_to_text(text)
            if len(text) > max_chars:
                text = text[:max_chars] + f"\n...[truncated, {len(text)-max_chars} more chars]"
            return {
                "success": True,
                "result": text,
                "url": url,
                "status": resp.status,
                "content_type": content_type,
                "size": len(data),
            }
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _html_to_text(html: str) -> str:
    """Convert HTML to plain text. Preserves paragraph breaks."""
    # Remove script/style content
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Convert block elements to newlines
    html = re.sub(r"</?(p|div|br|h[1-6]|li|tr|table)[^>]*>", "\n", html, flags=re.IGNORECASE)
    # Remove all other tags
    html = re.sub(r"<[^>]+>", "", html)
    # Decode common entities
    import html as html_module
    html = html_module.unescape(html)
    # Collapse whitespace
    lines = [l.strip() for l in html.split("\n")]
    lines = [l for l in lines if l]
    return "\n".join(lines)


# ============================================================
# Workflow tools (todo, plan, finish)
# ============================================================

def tool_todo_write(workspace: Path, args: Dict) -> Dict:
    """Write or update a structured TODO list for the current task.
    Each item has: id, content, status (pending/in_progress/completed)."""
    todos = args.get("todos", [])
    # Persist to workspace/.todos.json
    todo_file = workspace / ".todos.json"
    try:
        todo_file.write_text(json.dumps(todos, ensure_ascii=False, indent=2), encoding="utf-8")
        pending = sum(1 for t in todos if t.get("status") == "pending")
        in_progress = sum(1 for t in todos if t.get("status") == "in_progress")
        completed = sum(1 for t in todos if t.get("status") == "completed")
        return {
            "success": True,
            "result": f"updated TODO list ({len(todos)} items: {completed} done, {in_progress} active, {pending} pending)",
            "summary": {"total": len(todos), "pending": pending, "in_progress": in_progress, "completed": completed},
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_plan_write(workspace: Path, args: Dict) -> Dict:
    """Write a structured plan for a complex task. Persists to workspace/.plan.md."""
    plan = args.get("plan", "")
    title = args.get("title", "Task Plan")
    try:
        plan_file = workspace / ".plan.md"
        content = f"# {title}\n\nGenerated: {datetime.now().isoformat()}\n\n{plan}\n"
        plan_file.write_text(content, encoding="utf-8")
        return {"success": True, "result": f"plan saved ({len(plan)} chars)", "path": str(plan_file)}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# Skill self-evolution tools — let the AI write/update its own skills
# ============================================================

def make_skill_evolution_tools(skills_dir: Path):
    """Return tool functions bound to a specific skills_dir."""

    def tool_skill_create(args: Dict) -> Dict:
        name = (args.get("name") or "").strip()
        description = (args.get("description") or "").strip()
        body = args.get("body", "").strip()
        if not name or not re.match(r"^[a-z0-9-]+$", name):
            return {"success": False, "error": "name must match [a-z0-9-]+"}
        skill_dir = skills_dir / name
        if skill_dir.exists():
            return {"success": False, "error": f"skill {name} already exists; use skill_update to modify"}
        skill_dir.mkdir(parents=True)
        content = f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n"
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
        return {"success": True, "result": f"created skill '{name}'", "path": str(skill_dir / "SKILL.md")}

    def tool_skill_update(args: Dict) -> Dict:
        name = (args.get("name") or "").strip()
        description = args.get("description")
        body = args.get("body")
        if not name or not re.match(r"^[a-z0-9-]+$", name):
            return {"success": False, "error": "name must match [a-z0-9-]+"}
        skill_dir = skills_dir / name
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            return {"success": False, "error": f"skill {name} not found; use skill_create first"}
        old = skill_file.read_text(encoding="utf-8", errors="replace")
        # Parse existing
        existing_desc = ""
        existing_body = old
        if old.startswith("---"):
            end = old.find("\n---", 3)
            if end > 0:
                fm = old[3:end]
                existing_body = old[end + 4:].strip()
                for line in fm.splitlines():
                    if line.startswith("description:"):
                        existing_desc = line.split(":", 1)[1].strip()
        new_desc = description if description is not None else existing_desc
        new_body = body if body is not None else existing_body
        content = f"---\nname: {name}\ndescription: {new_desc}\n---\n\n{new_body}\n"
        skill_file.write_text(content, encoding="utf-8")
        return {"success": True, "result": f"updated skill '{name}'", "path": str(skill_file)}

    def tool_skill_read(args: Dict) -> Dict:
        name = (args.get("name") or "").strip()
        if not name or not re.match(r"^[a-z0-9-]+$", name):
            return {"success": False, "error": "invalid name"}
        skill_file = skills_dir / name / "SKILL.md"
        if not skill_file.exists():
            return {"success": False, "error": f"skill {name} not found"}
        content = skill_file.read_text(encoding="utf-8", errors="replace")
        return {"success": True, "result": content, "path": str(skill_file)}

    def tool_skill_list(args: Dict) -> Dict:
        if not skills_dir.exists():
            return {"success": True, "result": []}
        out = []
        for d in sorted(skills_dir.iterdir()):
            if not d.is_dir(): continue
            sf = d / "SKILL.md"
            if not sf.exists(): continue
            try:
                text = sf.read_text(encoding="utf-8", errors="replace")
                desc = ""
                if text.startswith("---"):
                    end = text.find("\n---", 3)
                    if end > 0:
                        for line in text[3:end].splitlines():
                            if line.startswith("description:"):
                                desc = line.split(":", 1)[1].strip()
                                break
                out.append({"name": d.name, "description": desc, "size": len(text)})
            except Exception:
                continue
        return {"success": True, "result": out}

    return {
        "skill_create": tool_skill_create,
        "skill_update": tool_skill_update,
        "skill_read": tool_skill_read,
        "skill_list": tool_skill_list,
    }


def make_custom_tool_runner(custom_tools_dir: Path):
    """Return a function that executes a user-defined custom tool.
    Custom tools are Python files in custom_tools_dir with a `run(args)` function."""
    def tool_run_custom(args: Dict) -> Dict:
        name = (args.get("tool_name") or "").strip()
        tool_args = args.get("args", {})
        if not name or not re.match(r"^[a-z0-9_-]+$", name):
            return {"success": False, "error": "invalid tool_name"}
        tool_file = custom_tools_dir / f"{name}.py"
        if not tool_file.exists():
            return {"success": False, "error": f"custom tool '{name}' not found"}
        try:
            # Load module
            import importlib.util
            spec = importlib.util.spec_from_file_location(f"custom_tool_{name}", tool_file)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if not hasattr(mod, "run"):
                return {"success": False, "error": f"tool '{name}' has no run(args) function"}
            result = mod.run(tool_args)
            if isinstance(result, dict):
                return {"success": True, "result": result, "tool": name}
            return {"success": True, "result": str(result), "tool": name}
        except Exception as e:
            return {"success": False, "error": f"tool '{name}' failed: {e}"}

    def tool_save_custom(args: Dict) -> Dict:
        """Save a custom Python tool that can be called later. The tool code must
        define a `run(args: dict) -> dict` function. Tools are saved to
        custom_tools/<name>.py and can be invoked via run_custom_tool."""
        name = (args.get("name") or "").strip()
        description = (args.get("description") or "").strip()
        code = args.get("code", "")
        if not name or not re.match(r"^[a-z0-9_-]+$", name):
            return {"success": False, "error": "name must match [a-z0-9_-]+"}
        if not code:
            return {"success": False, "error": "code required"}
        custom_tools_dir.mkdir(parents=True, exist_ok=True)
        tool_file = custom_tools_dir / f"{name}.py"
        # Prepend docstring with description
        if description:
            code = f'"""\nCustom tool: {name}\n{description}\n"""\n\n' + code
        tool_file.write_text(code, encoding="utf-8")
        # Save metadata
        meta_file = custom_tools_dir / f"{name}.meta.json"
        meta_file.write_text(json.dumps({
            "name": name,
            "description": description,
            "created_at": int(time.time()),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"success": True, "result": f"saved custom tool '{name}'", "path": str(tool_file)}

    def tool_list_custom(args: Dict) -> Dict:
        if not custom_tools_dir.exists():
            return {"success": True, "result": []}
        out = []
        for f in sorted(custom_tools_dir.glob("*.py")):
            meta_file = custom_tools_dir / f"{f.stem}.meta.json"
            desc = ""
            if meta_file.exists():
                try:
                    desc = json.loads(meta_file.read_text()).get("description", "")
                except Exception:
                    pass
            out.append({"name": f.stem, "description": desc, "size": f.stat().st_size})
        return {"success": True, "result": out}

    return {
        "run_custom_tool": tool_run_custom,
        "save_custom_tool": tool_save_custom,
        "list_custom_tools": tool_list_custom,
    }


# ============================================================
# Session tools — for multi-session task management
# ============================================================

# In-memory registry of background sessions
_active_sessions: Dict[str, Dict] = {}


def register_session(session_id: str, session_data: Dict):
    _active_sessions[session_id] = session_data


def get_session(session_id: str) -> Optional[Dict]:
    return _active_sessions.get(session_id)


def list_active_sessions() -> List[Dict]:
    return list(_active_sessions.values())


def remove_session(session_id: str):
    _active_sessions.pop(session_id, None)


def tool_sessions_list(workspace: Path, args: Dict) -> Dict:
    """List all active background sessions (running or recently completed)."""
    out = []
    for sid, s in _active_sessions.items():
        out.append({
            "id": sid,
            "title": s.get("title", ""),
            "status": s.get("status", "unknown"),
            "started_at": s.get("started_at"),
            "model": s.get("model", ""),
            "parent_session": s.get("parent_session"),
        })
    return {"success": True, "result": out, "total": len(out)}


def tool_session_status(workspace: Path, args: Dict) -> Dict:
    """Check the status of a session by id."""
    sid = args.get("session_id", "")
    if not sid:
        return {"success": False, "error": "session_id required"}
    s = _active_sessions.get(sid)
    if not s:
        return {"success": False, "error": f"session {sid} not found"}
    return {
        "success": True,
        "result": {
            "id": sid,
            "title": s.get("title", ""),
            "status": s.get("status", "unknown"),
            "started_at": s.get("started_at"),
            "completed_at": s.get("completed_at"),
            "model": s.get("model", ""),
            "result_summary": (s.get("result") or "")[:500] if s.get("status") == "completed" else None,
        }
    }


def tool_sessions_history(workspace: Path, args: Dict) -> Dict:
    """Get the message history of a session."""
    sid = args.get("session_id", "")
    if not sid:
        return {"success": False, "error": "session_id required"}
    s = _active_sessions.get(sid)
    if not s:
        return {"success": False, "error": f"session {sid} not found"}
    return {
        "success": True,
        "result": s.get("messages", []),
        "status": s.get("status"),
    }


# ============================================================
# Tool definitions (OpenAI function-calling schema)
# ============================================================

def build_tool_definitions() -> List[Dict]:
    """Return the full list of tool definitions for the LLM."""
    return [
        # === Time ===
        {"type": "function", "function": {
            "name": "get_current_time",
            "description": "获取当前日期和时间。当用户询问时间、日期、星期几，或需要知道'现在'时调用。",
            "parameters": {"type": "object", "properties": {
                "timezone": {"type": "string", "description": "时区，如 'Asia/Shanghai'。默认 Asia/Shanghai。"}
            }, "required": []},
        }},
        # === Code execution ===
        {"type": "function", "function": {
            "name": "run_python",
            "description": "执行 Python 代码做计算、画图、数据处理、写文件。可访问标准库和已安装的包。工作目录为 workspace。临时任务代码无需保存到文件，直接执行即可。如果代码较长且有保存价值，可以用 write_file 保存。",
            "parameters": {"type": "object", "properties": {
                "code": {"type": "string", "description": "Python 代码。print() 输出会被捕获。"}
            }, "required": ["code"]},
        }},
        {"type": "function", "function": {
            "name": "run_shell",
            "description": "执行终端命令（ls/cat/echo/grep/python/pip 等）。注意：这不是网络搜索。返回 stdout+stderr。危险命令会被阻止。",
            "parameters": {"type": "object", "properties": {
                "command": {"type": "string", "description": "shell 命令"}
            }, "required": ["command"]},
        }},
        # === File operations ===
        {"type": "function", "function": {
            "name": "read_file",
            "description": "读取工作区文件内容。可指定 offset 和 limit 读取特定行范围。默认读全文（截断到 50KB）。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "文件路径（相对 workspace）"},
                "offset": {"type": "integer", "description": "起始行号（1-indexed），默认 0=从头"},
                "limit": {"type": "integer", "description": "读取的行数，0=全部"}
            }, "required": ["path"]},
        }},
        {"type": "function", "function": {
            "name": "write_file",
            "description": "写入/创建文件。默认覆盖；set append=true 追加。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "内容"},
                "append": {"type": "boolean", "description": "true=追加到末尾，false=覆盖（默认）"}
            }, "required": ["path", "content"]},
        }},
        {"type": "function", "function": {
            "name": "str_replace",
            "description": "在文件中查找 old_str 并替换为 new_str。默认只替换第一处；set replace_all=true 替换所有。如果 old_str 出现多次且未设 replace_all，会报错（要求提供更多上下文以唯一定位）。比 edit_file 更严格、更安全。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"},
                "old_str": {"type": "string", "description": "要替换的文本（必须精确匹配，包括空白）"},
                "new_str": {"type": "string", "description": "替换后的文本"},
                "replace_all": {"type": "boolean", "description": "true=替换所有出现，false=仅第一处（默认）"}
            }, "required": ["path", "old_str", "new_str"]},
        }},
        {"type": "function", "function": {
            "name": "regex_replace",
            "description": "用正则表达式替换文件中的文本。flags 可包含 g/i/m/s（全局/忽略大小写/多行/单行）。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"},
                "pattern": {"type": "string", "description": "正则表达式"},
                "replacement": {"type": "string", "description": "替换文本，支持 $1, $2 等捕获组"},
                "flags": {"type": "string", "description": "标志位组合，如 'gi'。默认 'g'"}
            }, "required": ["path", "pattern", "replacement"]},
        }},
        {"type": "function", "function": {
            "name": "multi_edit",
            "description": "对单个文件应用多个编辑（事务性：任一失败则全部回滚）。每个 edit 是 {old_str, new_str}。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"},
                "edits": {"type": "array", "items": {"type": "object", "properties": {
                    "old_str": {"type": "string"},
                    "new_str": {"type": "string"}
                }, "required": ["old_str", "new_str"]}}
            }, "required": ["path", "edits"]},
        }},
        {"type": "function", "function": {
            "name": "apply_patch",
            "description": "对文件应用 unified diff 补丁。适合批量修改、版本回滚等。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"},
                "patch": {"type": "string", "description": "unified diff 格式补丁"}
            }, "required": ["path", "patch"]},
        }},
        {"type": "function", "function": {
            "name": "file_append",
            "description": "向文件末尾追加文本（不存在则创建）。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"}
            }, "required": ["path", "content"]},
        }},
        {"type": "function", "function": {
            "name": "file_prepend",
            "description": "在文件开头插入文本（不存在则创建）。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"}
            }, "required": ["path", "content"]},
        }},
        {"type": "function", "function": {
            "name": "insert_lines",
            "description": "在指定行号（1-indexed）插入文本。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"},
                "line": {"type": "integer", "description": "插入位置（1-indexed）"},
                "content": {"type": "string"}
            }, "required": ["path", "line", "content"]},
        }},
        {"type": "function", "function": {
            "name": "delete_lines",
            "description": "删除指定行范围（1-indexed, inclusive）。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"},
                "start": {"type": "integer"},
                "end": {"type": "integer"}
            }, "required": ["path", "start", "end"]},
        }},
        {"type": "function", "function": {
            "name": "file_move",
            "description": "移动或重命名文件/目录。",
            "parameters": {"type": "object", "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"}
            }, "required": ["source", "destination"]},
        }},
        {"type": "function", "function": {
            "name": "file_copy",
            "description": "复制文件或目录（递归）。",
            "parameters": {"type": "object", "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"}
            }, "required": ["source", "destination"]},
        }},
        {"type": "function", "function": {
            "name": "delete_file",
            "description": "删除文件或目录（目录需 recursive=true）。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"},
                "recursive": {"type": "boolean", "description": "删除目录时必须为 true"}
            }, "required": ["path"]},
        }},
        {"type": "function", "function": {
            "name": "make_directory",
            "description": "创建目录（含父目录）。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"}
            }, "required": ["path"]},
        }},
        {"type": "function", "function": {
            "name": "file_stat",
            "description": "获取文件/目录的元数据（大小、修改时间、权限等）。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"}
            }, "required": ["path"]},
        }},
        {"type": "function", "function": {
            "name": "file_tree",
            "description": "递归列出目录树，可按 glob 过滤文件。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "默认 '.'"},
                "max_depth": {"type": "integer", "description": "最大深度，默认 3"},
                "include": {"type": "string", "description": "glob 过滤，如 '*.py'"}
            }, "required": []},
        }},
        {"type": "function", "function": {
            "name": "list_directory",
            "description": "列出目录内容（不递归）。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "默认 '.'"}
            }, "required": []},
        }},
        # === Search ===
        {"type": "function", "function": {
            "name": "grep",
            "description": "在文件内容中搜索正则表达式（类似 ripgrep）。返回匹配的行（file:line:content）。",
            "parameters": {"type": "object", "properties": {
                "pattern": {"type": "string", "description": "正则表达式"},
                "path": {"type": "string", "description": "搜索路径，默认 '.'"},
                "case_insensitive": {"type": "boolean"},
                "include": {"type": "string", "description": "文件名 glob，如 '*.py'"},
                "max_results": {"type": "integer", "description": "默认 100"}
            }, "required": ["pattern"]},
        }},
        {"type": "function", "function": {
            "name": "glob",
            "description": "按 glob 模式查找文件（如 '**/*.py'）。",
            "parameters": {"type": "object", "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string", "description": "默认 '.'"}
            }, "required": ["pattern"]},
        }},
        # === Web ===
        {"type": "function", "function": {
            "name": "web_search",
            "description": "搜索互联网获取实时信息。优先使用 MCP open-webSearch 后端，失败回退 DuckDuckGo。仅用于需要最新新闻、不确定事实、外部数据时。",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"}
            }, "required": ["query"]},
        }},
        {"type": "function", "function": {
            "name": "web_fetch",
            "description": "抓取 URL 内容并返回为文本。自动把 HTML 转为纯文本。适合读文章、API 文档、GitHub README 等。",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string"},
                "raw_html": {"type": "boolean", "description": "true=返回原始 HTML"},
                "max_chars": {"type": "integer", "description": "默认 20000"}
            }, "required": ["url"]},
        }},
        # === Package install ===
        {"type": "function", "function": {
            "name": "install_package",
            "description": "用 pip 安装 Python 包。",
            "parameters": {"type": "object", "properties": {
                "package": {"type": "string", "description": "如 'requests'、'numpy==1.24.0'"}
            }, "required": ["package"]},
        }},
        # === Workflow ===
        {"type": "function", "function": {
            "name": "todo_write",
            "description": "更新当前任务的 TODO 列表。每个 item: {id, content, status: pending|in_progress|completed}。用于跟踪多步骤任务的进度。",
            "parameters": {"type": "object", "properties": {
                "todos": {"type": "array", "items": {"type": "object", "properties": {
                    "id": {"type": "string"},
                    "content": {"type": "string"},
                    "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}
                }, "required": ["id", "content", "status"]}}
            }, "required": ["todos"]},
        }},
        {"type": "function", "function": {
            "name": "plan_write",
            "description": "保存复杂任务的执行计划到 workspace/.plan.md。",
            "parameters": {"type": "object", "properties": {
                "title": {"type": "string"},
                "plan": {"type": "string", "description": "计划内容（Markdown）"}
            }, "required": ["plan"]},
        }},
        # === Skill self-evolution ===
        {"type": "function", "function": {
            "name": "skill_create",
            "description": "创建新的技能（SKILL.md 文件）。技能是 AI 可以在后续对话中参考的指令集。用于自进化：当 AI 发现某类问题反复出现，可以创建技能保存解决方案。技能名只能包含小写字母、数字和短横线。",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string", "description": "技能名（如 'python-debug'）"},
                "description": {"type": "string", "description": "触发条件描述：什么情况下应该使用这个技能"},
                "body": {"type": "string", "description": "技能正文：详细的指令、步骤、注意事项"}
            }, "required": ["name", "description", "body"]},
        }},
        {"type": "function", "function": {
            "name": "skill_update",
            "description": "更新已有技能的描述或正文。用于技能迭代改进——AI 在使用过程中发现技能不够好时可以自己修改。",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string"},
                "description": {"type": "string", "description": "新的描述（可选，留空则不变）"},
                "body": {"type": "string", "description": "新的正文（可选，留空则不变）"}
            }, "required": ["name"]},
        }},
        {"type": "function", "function": {
            "name": "skill_read",
            "description": "读取某个技能的完整内容。",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string"}
            }, "required": ["name"]},
        }},
        {"type": "function", "function": {
            "name": "skill_list",
            "description": "列出所有已安装的技能。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }},
        # === Custom tools (AI can write its own tools) ===
        {"type": "function", "function": {
            "name": "save_custom_tool",
            "description": "保存一个自定义 Python 工具到 custom_tools/<name>.py。代码必须定义 run(args: dict) -> dict 函数。这是自进化的核心：AI 可以把反复使用的逻辑封装成工具，后续直接调用。工具名只能包含小写字母、数字、下划线、短横线。",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string", "description": "工具名（如 'json_formatter'）"},
                "description": {"type": "string", "description": "工具描述"},
                "code": {"type": "string", "description": "Python 代码，必须定义 run(args) 函数"}
            }, "required": ["name", "code"]},
        }},
        {"type": "function", "function": {
            "name": "run_custom_tool",
            "description": "调用之前保存的自定义工具。",
            "parameters": {"type": "object", "properties": {
                "tool_name": {"type": "string"},
                "args": {"type": "object", "description": "传给工具 run() 函数的参数"}
            }, "required": ["tool_name"]},
        }},
        {"type": "function", "function": {
            "name": "list_custom_tools",
            "description": "列出所有已保存的自定义工具。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }},
        # === Multi-session management ===
        {"type": "function", "function": {
            "name": "sessions_list",
            "description": "列出所有正在运行或最近完成的后台会话。多会话系统允许同时处理不同任务（如一个研究旅行、一个写代码），互不干扰。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }},
        {"type": "function", "function": {
            "name": "session_status",
            "description": "查询某个后台会话的状态。",
            "parameters": {"type": "object", "properties": {
                "session_id": {"type": "string"}
            }, "required": ["session_id"]},
        }},
        {"type": "function", "function": {
            "name": "sessions_history",
            "description": "获取某个后台会话的对话历史。",
            "parameters": {"type": "object", "properties": {
                "session_id": {"type": "string"}
            }, "required": ["session_id"]},
        }},
        # === Memory tools ===
        {"type": "function", "function": {
            "name": "memory_search",
            "description": "检索长期记忆，查找与查询相关的记忆片段。",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "description": "默认 5"}
            }, "required": ["query"]},
        }},
        {"type": "function", "function": {
            "name": "memory_add",
            "description": "手动添加一条长期记忆。",
            "parameters": {"type": "object", "properties": {
                "content": {"type": "string"},
                "category": {"type": "string", "description": "identity/preference/goal/skill/relationship/other"}
            }, "required": ["content"]},
        }},
    ]


# ============================================================
# Tool dispatcher
# ============================================================

def make_dispatcher(workspace: Path, skills_dir: Path, custom_tools_dir: Path,
                    memory_search_fn=None, memory_add_fn=None,
                    mcp_call_fn=None, web_search_fn=None,
                    sessions_spawn_fn=None):
    """Build a dispatcher that routes tool names to implementations.
    Returns a function (name, args) -> Dict."""
    skill_tools = make_skill_evolution_tools(skills_dir)
    custom_tools = make_custom_tool_runner(custom_tools_dir)

    def dispatch(name: str, args: Dict) -> Dict:
        try:
            # Time
            if name == "get_current_time":
                tz_name = args.get("timezone", "Asia/Shanghai")
                try:
                    from zoneinfo import ZoneInfo
                    tz = ZoneInfo(tz_name)
                except Exception:
                    tz = timezone(timedelta(hours=8))
                now = datetime.now(tz)
                return {
                    "success": True,
                    "result": now.strftime("%Y-%m-%d %H:%M:%S %Z") + f" ({tz_name})",
                    "iso": now.isoformat(),
                    "weekday": ["周一","周二","周三","周四","周五","周六","周日"][now.weekday()],
                }
            # Code execution
            if name == "run_python":
                return _run_python(workspace, args.get("code", ""))
            if name == "run_shell":
                return _run_shell(workspace, args.get("command", ""))
            # File ops
            if name == "read_file":
                return tool_read_file(workspace, args)
            if name == "write_file":
                return tool_write_file(workspace, args)
            if name == "str_replace":
                return tool_str_replace(workspace, args)
            if name == "regex_replace":
                return tool_regex_replace(workspace, args)
            if name == "multi_edit":
                return tool_multi_edit(workspace, args)
            if name == "apply_patch":
                return tool_apply_patch(workspace, args)
            if name == "file_append":
                return tool_file_append(workspace, args)
            if name == "file_prepend":
                return tool_file_prepend(workspace, args)
            if name == "insert_lines":
                return tool_insert_lines(workspace, args)
            if name == "delete_lines":
                return tool_delete_lines(workspace, args)
            if name == "file_move":
                return tool_file_move(workspace, args)
            if name == "file_copy":
                return tool_file_copy(workspace, args)
            if name == "delete_file":
                return tool_delete_file(workspace, args)
            if name == "make_directory":
                return tool_make_directory(workspace, args)
            if name == "file_stat":
                return tool_file_stat(workspace, args)
            if name == "file_tree":
                return tool_file_tree(workspace, args)
            if name == "list_directory":
                return _list_directory(workspace, args)
            # Search
            if name == "grep":
                return tool_grep(workspace, args)
            if name == "glob":
                return tool_glob(workspace, args)
            # Web
            if name == "web_search":
                if web_search_fn:
                    return web_search_fn(args)
                return {"success": False, "error": "web_search not configured"}
            if name == "web_fetch":
                return tool_web_fetch(workspace, args)
            # Package install
            if name == "install_package":
                return _install_package(args.get("package", ""))
            # Workflow
            if name == "todo_write":
                return tool_todo_write(workspace, args)
            if name == "plan_write":
                return tool_plan_write(workspace, args)
            # Skills
            if name == "skill_create":
                return skill_tools["skill_create"](args)
            if name == "skill_update":
                return skill_tools["skill_update"](args)
            if name == "skill_read":
                return skill_tools["skill_read"](args)
            if name == "skill_list":
                return skill_tools["skill_list"](args)
            # Custom tools
            if name == "save_custom_tool":
                return custom_tools["save_custom_tool"](args)
            if name == "run_custom_tool":
                return custom_tools["run_custom_tool"](args)
            if name == "list_custom_tools":
                return custom_tools["list_custom_tools"](args)
            # Sessions
            if name == "sessions_list":
                return tool_sessions_list(workspace, args)
            if name == "session_status":
                return tool_session_status(workspace, args)
            if name == "sessions_history":
                return tool_sessions_history(workspace, args)
            if name == "sessions_spawn":
                if sessions_spawn_fn:
                    return sessions_spawn_fn(args)
                return {"success": False, "error": "sessions_spawn not configured"}
            if name == "sessions_send":
                if sessions_spawn_fn:
                    return sessions_spawn_fn(args)
                return {"success": False, "error": "sessions_send not configured"}
            # Memory
            if name == "memory_search":
                if memory_search_fn:
                    return {"success": True, "result": memory_search_fn(args.get("query", ""), top_k=int(args.get("top_k", 5)))}
                return {"success": False, "error": "memory_search not configured"}
            if name == "memory_add":
                if memory_add_fn:
                    return memory_add_fn(args)
                return {"success": False, "error": "memory_add not configured"}
            return {"success": False, "error": f"unknown tool: {name}"}
        except Exception as e:
            return {"success": False, "error": f"tool '{name}' crashed: {e}"}

    return dispatch


def _run_python(workspace: Path, code: str) -> Dict:
    if not code:
        return {"success": False, "error": "no code provided"}
    _check_workspace(workspace)
    script_name = f"script_{int(time.time()*1000)}_{os.getpid()}.py"
    script_path = workspace / script_name
    script_path.write_text(code, encoding="utf-8")
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(script_path)],
            capture_output=True,
            timeout=60,
            cwd=str(workspace),
            env=env,
            encoding="utf-8",
            errors="replace",
        )
        output = result.stdout or ""
        if result.stderr:
            output += "\n[STDERR]\n" + result.stderr
        if result.returncode != 0:
            output += f"\n[Exit code: {result.returncode}]"
        if len(output) > 10000:
            output = output[:10000] + "\n...[output truncated]"
        return {"success": result.returncode == 0, "result": output or "(no output)"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "执行超时（超过60秒）"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        try: script_path.unlink()
        except: pass


SHELL_BLOCKLIST = [
    "rm -rf /", "rm -fr /", "sudo ", "chmod 777 /", "mkfs", "dd if=/dev/",
    ":(){", "fork bomb", "shutdown", "reboot", "halt", "poweroff",
    "> /dev/sd", "kill -9 1", "format c:", "del /f /s /q c:\\",
]


def _run_shell(workspace: Path, cmd: str) -> Dict:
    if not cmd:
        return {"success": False, "error": "no command provided"}
    cmd_lower = cmd.lower()
    for blocked in SHELL_BLOCKLIST:
        if blocked in cmd_lower:
            return {"success": False, "error": f"命令被安全策略阻止（包含: {blocked}）"}
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=60, cwd=str(workspace),
            encoding="utf-8", errors="replace",
        )
        output = result.stdout or ""
        if result.stderr:
            output += "\n[STDERR]\n" + result.stderr
        if len(output) > 8000:
            output = output[:8000] + "\n...[output truncated]"
        return {"success": result.returncode == 0, "result": output or "(no output)"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "命令执行超时（超过60秒）"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _list_directory(workspace: Path, args: Dict) -> Dict:
    path = args.get("path", ".")
    fp = _safe_resolve(workspace, path)
    if not fp.exists():
        return {"success": False, "error": f"目录不存在: {path}"}
    if not fp.is_dir():
        return {"success": False, "error": f"不是目录: {path}"}
    items = []
    for item in sorted(fp.iterdir()):
        items.append({
            "name": item.name,
            "type": "dir" if item.is_dir() else "file",
            "size": item.stat().st_size if item.is_file() else None,
        })
    return {"success": True, "result": items, "path": str(fp)}


def _install_package(package: str) -> Dict:
    if not package:
        return {"success": False, "error": "no package provided"}
    if any(c in package for c in [";", "&", "|", "`", "$"]):
        return {"success": False, "error": "包名包含非法字符"}
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            capture_output=True, text=True, timeout=180,
            encoding="utf-8", errors="replace",
        )
        output = result.stdout or ""
        if result.stderr:
            output += "\n" + result.stderr
        if len(output) > 3000:
            output = output[:3000] + "\n...[output truncated]"
        return {"success": result.returncode == 0, "result": output or "(no output)"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "安装超时（超过180秒）"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# Lightweight local embedding (~zero deps, ~0MB)
# ============================================================
# A simple but effective embedding based on character n-grams + word hashing.
# For 200MB-class neural embedding, we'd use sentence-transformers with a small
# model like 'paraphrase-MiniLM-L3-v2' (~30MB). But to avoid the heavy dep,
# we provide a TF-IDF + hashing-based embedding that's good enough for personal
# RAG at < 1000 documents.

class LocalEmbedder:
    """Lightweight text embedder using TF-IDF + character n-grams + word hashing.
    Vector dimension: 512. Zero external deps."""
    def __init__(self, dim: int = 512):
        self.dim = dim
        self.vocab: Dict[str, int] = {}  # term -> idx (built incrementally)
        self.idf: Dict[int, float] = {}
        self.doc_count = 0

    def _tokenize(self, text: str) -> List[str]:
        text = text.lower()
        tokens = []
        # Word tokens (latin)
        for m in re.findall(r"[a-z0-9]+", text):
            if len(m) >= 2:
                tokens.append(m)
        # Chinese character bigrams
        cjk = re.findall(r"[\u4e00-\u9fff]", text)
        for i in range(len(cjk) - 1):
            tokens.append(cjk[i] + cjk[i+1])
        # Single CJK chars (fallback)
        if len(cjk) < 4:
            for c in cjk:
                tokens.append(c)
        return tokens

    def embed(self, text: str) -> List[float]:
        """Embed text into a fixed-size vector."""
        tokens = self._tokenize(text)
        if not tokens:
            return [0.0] * self.dim
        # Term frequency
        from collections import Counter
        tf = Counter(tokens)
        vec = [0.0] * self.dim
        for term, count in tf.items():
            # Hash term to dim
            h = int(hashlib.md5(term.encode()).hexdigest(), 16) % self.dim
            # IDF (default 1.0 if unseen)
            idf = self.idf.get(h, 1.0)
            # TF-IDF weighted, log-scaled
            vec[h] = (1.0 + __import__('math').log(count)) * idf
        # L2 normalize
        norm = __import__('math').sqrt(sum(v*v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def fit(self, texts: List[str]):
        """Compute IDF from a corpus."""
        self.doc_count = len(texts)
        term_doc_count: Dict[int, int] = {}
        for text in texts:
            tokens = set(self._tokenize(text))
            for term in tokens:
                h = int(hashlib.md5(term.encode()).hexdigest(), 16) % self.dim
                term_doc_count[h] = term_doc_count.get(h, 0) + 1
        for h, c in term_doc_count.items():
            self.idf[h] = __import__('math').log((self.doc_count + 1) / (c + 1)) + 1.0

    def cosine(self, v1: List[float], v2: List[float]) -> float:
        return sum(a*b for a, b in zip(v1, v2))


# Global embedder instance (lazy-loaded)
_global_embedder: Optional[LocalEmbedder] = None


def get_embedder() -> LocalEmbedder:
    global _global_embedder
    if _global_embedder is None:
        _global_embedder = LocalEmbedder(dim=512)
    return _global_embedder


def embed_text(text: str) -> List[float]:
    return get_embedder().embed(text)
