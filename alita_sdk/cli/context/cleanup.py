"""
Session cleanup utilities for CLI context management.

Handles purging old sessions to prevent disk space issues.
"""

import os
import shutil
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


def get_sessions_dir(alita_dir: str = '.alita') -> Path:
    """
    Get the sessions directory path.
    
    Args:
        alita_dir: Base Alita directory
        
    Returns:
        Path to sessions directory
    """
    # Expand ~ for home directory
    if alita_dir.startswith('~'):
        alita_dir = os.path.expanduser(alita_dir)
    return Path(alita_dir) / 'sessions'


def list_sessions_with_age(alita_dir: str = '.alita') -> List[Tuple[str, float, datetime]]:
    """
    List all sessions with their age in days.
    
    Args:
        alita_dir: Base Alita directory
        
    Returns:
        List of tuples: (session_id, age_days, modified_time)
    """
    sessions_dir = get_sessions_dir(alita_dir)
    
    if not sessions_dir.exists():
        return []
    
    sessions = []
    now = datetime.now(timezone.utc)
    
    for session_path in sessions_dir.iterdir():
        if not session_path.is_dir():
            continue
        
        session_id = session_path.name
        
        # Get modification time (most recent file in session)
        try:
            mtime = max(
                f.stat().st_mtime
                for f in session_path.rglob('*')
                if f.is_file()
            )
            modified = datetime.fromtimestamp(mtime, tz=timezone.utc)
            age_days = (now - modified).total_seconds() / 86400
            sessions.append((session_id, age_days, modified))
        except (ValueError, OSError):
            # No files or error accessing - use directory mtime
            try:
                mtime = session_path.stat().st_mtime
                modified = datetime.fromtimestamp(mtime, tz=timezone.utc)
                age_days = (now - modified).total_seconds() / 86400
                sessions.append((session_id, age_days, modified))
            except OSError:
                continue
    
    # Sort by modification time (oldest first)
    sessions.sort(key=lambda x: x[2])
    
    return sessions


def purge_old_sessions(
    max_age_days: int = 30,
    max_sessions: int = 50,
    alita_dir: str = '.alita',
    dry_run: bool = False
) -> Tuple[int, int]:
    """
    Purge old sessions based on age and count limits.
    
    Args:
        max_age_days: Maximum age in days before a session is purged
        max_sessions: Maximum number of sessions to keep
        alita_dir: Base Alita directory
        dry_run: If True, only report what would be deleted
        
    Returns:
        Tuple of (sessions_deleted, bytes_freed)
    """
    sessions_dir = get_sessions_dir(alita_dir)
    
    if not sessions_dir.exists():
        return 0, 0
    
    sessions = list_sessions_with_age(alita_dir)
    
    if not sessions:
        return 0, 0
    
    to_delete = []
    
    # Mark sessions older than max_age_days for deletion
    for session_id, age_days, modified in sessions:
        if age_days > max_age_days:
            to_delete.append(session_id)
    
    # If we still have too many sessions, delete oldest ones
    remaining = [s for s in sessions if s[0] not in to_delete]
    if len(remaining) > max_sessions:
        # Sort remaining by age (oldest first) and mark excess for deletion
        excess_count = len(remaining) - max_sessions
        for session_id, age_days, modified in remaining[:excess_count]:
            if session_id not in to_delete:
                to_delete.append(session_id)
    
    # Delete marked sessions
    deleted_count = 0
    bytes_freed = 0
    
    for session_id in to_delete:
        session_path = sessions_dir / session_id
        
        if not session_path.exists():
            continue
        
        # Calculate size before deletion
        try:
            session_size = sum(
                f.stat().st_size
                for f in session_path.rglob('*')
                if f.is_file()
            )
        except OSError:
            session_size = 0
        
        if dry_run:
            logger.info(f"Would delete session: {session_id} ({session_size} bytes)")
        else:
            try:
                shutil.rmtree(session_path)
                deleted_count += 1
                bytes_freed += session_size
                logger.debug(f"Deleted session: {session_id}")
            except OSError as e:
                logger.warning(f"Failed to delete session {session_id}: {e}")
    
    if deleted_count > 0:
        logger.info(f"Purged {deleted_count} old sessions, freed {bytes_freed} bytes")
    
    return deleted_count, bytes_freed


def get_session_disk_usage(alita_dir: str = '.alita') -> Tuple[int, int]:
    """
    Get disk usage statistics for sessions.
    
    Args:
        alita_dir: Base Alita directory
        
    Returns:
        Tuple of (session_count, total_bytes)
    """
    sessions_dir = get_sessions_dir(alita_dir)
    
    if not sessions_dir.exists():
        return 0, 0
    
    session_count = 0
    total_bytes = 0
    
    for session_path in sessions_dir.iterdir():
        if not session_path.is_dir():
            continue
        
        session_count += 1
        
        try:
            session_size = sum(
                f.stat().st_size
                for f in session_path.rglob('*')
                if f.is_file()
            )
            total_bytes += session_size
        except OSError:
            continue
    
    return session_count, total_bytes
