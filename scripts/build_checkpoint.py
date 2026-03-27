#!/usr/bin/env python3
"""Build checkpoint/resume for multi-phase course builds.

Saves progress during long-running course builds so they can be
resumed after failures instead of starting over.

Usage:
    from build_checkpoint import CheckpointManager

    mgr = CheckpointManager(course_id=12345)

    # Start a new build
    cp = mgr.create(total_items=30, config={"module": "Module 1"})

    # Mark items complete as they succeed
    for page in pages:
        build_page(page)
        mgr.mark_complete(page["slug"])

    # If it crashes, later resume:
    cp = mgr.get_latest()
    remaining = mgr.get_remaining(all_items)
    for page in remaining:
        build_page(page)
        mgr.mark_complete(page["slug"])

    mgr.finish()

CLI:
    python build_checkpoint.py --list                    # Show all checkpoints
    python build_checkpoint.py --status <course_id>      # Latest checkpoint for course
    python build_checkpoint.py --clean                   # Remove completed checkpoints
    python build_checkpoint.py --clean-all               # Remove ALL checkpoints
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

CHECKPOINT_DIR = Path.home() / ".idw" / "checkpoints"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)


class CheckpointManager:
    """Manages build checkpoints for a specific course."""

    def __init__(self, course_id):
        self.course_id = str(course_id)
        self._checkpoint = None
        self._path = None

    def create(self, total_items, config=None):
        """Create a new checkpoint for a build."""
        now = datetime.now(timezone.utc)
        self._checkpoint = {
            "course_id": self.course_id,
            "config": config or {},
            "total_items": total_items,
            "completed_items": [],
            "failed_items": [],
            "status": "in_progress",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "error": None,
        }
        ts = now.strftime("%Y%m%d_%H%M%S")
        self._path = CHECKPOINT_DIR / f"{self.course_id}_{ts}.json"
        self._save()
        return self._checkpoint

    def get_latest(self):
        """Get the most recent checkpoint for this course (any status)."""
        files = sorted(CHECKPOINT_DIR.glob(f"{self.course_id}_*.json"), reverse=True)
        if not files:
            return None
        self._path = files[0]
        self._checkpoint = json.loads(files[0].read_text(encoding="utf-8"))
        return self._checkpoint

    def get_latest_incomplete(self):
        """Get the most recent in_progress or failed checkpoint."""
        files = sorted(CHECKPOINT_DIR.glob(f"{self.course_id}_*.json"), reverse=True)
        for f in files:
            cp = json.loads(f.read_text(encoding="utf-8"))
            if cp["status"] in ("in_progress", "failed"):
                self._path = f
                self._checkpoint = cp
                return cp
        return None

    def mark_complete(self, item_id):
        """Mark an item as successfully completed."""
        if not self._checkpoint:
            raise RuntimeError("No active checkpoint")
        if item_id not in self._checkpoint["completed_items"]:
            self._checkpoint["completed_items"].append(item_id)
        self._checkpoint["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save()

    def mark_failed(self, item_id, error_msg=None):
        """Mark an item as failed."""
        if not self._checkpoint:
            raise RuntimeError("No active checkpoint")
        if item_id not in self._checkpoint["failed_items"]:
            self._checkpoint["failed_items"].append(item_id)
        if error_msg:
            self._checkpoint["error"] = error_msg
        self._checkpoint["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save()

    def get_remaining(self, all_items):
        """Given a list of all item IDs, return those not yet completed."""
        if not self._checkpoint:
            return all_items
        done = set(self._checkpoint["completed_items"])
        return [item for item in all_items if item not in done]

    def finish(self):
        """Mark the build as completed."""
        if not self._checkpoint:
            raise RuntimeError("No active checkpoint")
        self._checkpoint["status"] = "completed"
        self._checkpoint["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save()

    def fail(self, error_msg):
        """Mark the build as failed."""
        if not self._checkpoint:
            raise RuntimeError("No active checkpoint")
        self._checkpoint["status"] = "failed"
        self._checkpoint["error"] = error_msg
        self._checkpoint["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save()

    @property
    def progress(self):
        """Return (completed, total) tuple."""
        if not self._checkpoint:
            return (0, 0)
        return (len(self._checkpoint["completed_items"]), self._checkpoint["total_items"])

    @property
    def progress_pct(self):
        """Return completion percentage."""
        done, total = self.progress
        return round((done / total) * 100, 1) if total > 0 else 0.0

    def _save(self):
        self._path.write_text(json.dumps(self._checkpoint, indent=2), encoding="utf-8")


def list_all():
    """List all checkpoints."""
    files = sorted(CHECKPOINT_DIR.glob("*.json"))
    if not files:
        print("No checkpoints found.")
        return
    print(f"{'Course':<12} {'Status':<14} {'Progress':<12} {'Created':<20} {'Updated':<20}")
    print("─" * 78)
    for f in files:
        cp = json.loads(f.read_text(encoding="utf-8"))
        done = len(cp.get("completed_items", []))
        total = cp.get("total_items", 0)
        pct = f"{done}/{total} ({round(done/total*100) if total else 0}%)"
        print(f"{cp['course_id']:<12} {cp['status']:<14} {pct:<12} {cp['created_at'][:19]:<20} {cp['updated_at'][:19]:<20}")
        if cp.get("error"):
            print(f"  └─ Error: {cp['error']}")


def show_status(course_id):
    """Show latest checkpoint for a course."""
    mgr = CheckpointManager(course_id)
    cp = mgr.get_latest()
    if not cp:
        print(f"No checkpoints for course {course_id}")
        return
    done, total = mgr.progress
    print(f"Course: {cp['course_id']}")
    print(f"Status: {cp['status']}")
    print(f"Progress: {done}/{total} ({mgr.progress_pct}%)")
    print(f"Created: {cp['created_at'][:19]}")
    print(f"Updated: {cp['updated_at'][:19]}")
    if cp.get("config"):
        print(f"Config: {json.dumps(cp['config'])}")
    if cp.get("completed_items"):
        print(f"Completed: {', '.join(cp['completed_items'][:10])}")
        if len(cp["completed_items"]) > 10:
            print(f"  ... and {len(cp['completed_items']) - 10} more")
    if cp.get("failed_items"):
        print(f"Failed: {', '.join(cp['failed_items'])}")
    if cp.get("error"):
        print(f"Error: {cp['error']}")


def clean(all_checkpoints=False):
    """Remove completed (or all) checkpoints."""
    files = list(CHECKPOINT_DIR.glob("*.json"))
    removed = 0
    for f in files:
        if all_checkpoints:
            f.unlink()
            removed += 1
        else:
            cp = json.loads(f.read_text(encoding="utf-8"))
            if cp.get("status") == "completed":
                f.unlink()
                removed += 1
    print(f"Removed {removed} checkpoint(s).")


def main():
    parser = argparse.ArgumentParser(description="Build checkpoint manager")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="List all checkpoints")
    group.add_argument("--status", metavar="COURSE_ID", help="Show status for course")
    group.add_argument("--clean", action="store_true", help="Remove completed checkpoints")
    group.add_argument("--clean-all", action="store_true", help="Remove ALL checkpoints")
    args = parser.parse_args()

    if args.list:
        list_all()
    elif args.status:
        show_status(args.status)
    elif args.clean:
        clean(all_checkpoints=False)
    elif args.clean_all:
        clean(all_checkpoints=True)


if __name__ == "__main__":
    main()
