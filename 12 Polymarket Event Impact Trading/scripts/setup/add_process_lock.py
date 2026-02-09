#!/usr/bin/env python3
"""
Add process locking to prevent duplicate collector instances.
This patch adds a PID file mechanism to gdelt_collector.py
"""

import sys
from pathlib import Path

# Lock file content to add to gdelt_collector.py
LOCK_MECHANISM = '''
class ProcessLock:
    """Simple PID file lock to prevent duplicate processes."""

    def __init__(self, lock_file: str):
        self.lock_file = Path(lock_file)
        self.locked = False

    def acquire(self) -> bool:
        """Acquire lock. Returns True if successful, False if already locked."""
        if self.lock_file.exists():
            # Check if the process is still running
            try:
                with open(self.lock_file, 'r') as f:
                    old_pid = int(f.read().strip())

                # Check if process exists
                import os
                import errno
                try:
                    os.kill(old_pid, 0)  # Doesn't actually kill, just checks existence
                    logger.warning(f"Another instance is running (PID: {old_pid})")
                    return False
                except OSError as e:
                    if e.errno == errno.ESRCH:  # No such process
                        logger.info(f"Stale lock file found (PID {old_pid}), removing")
                        self.lock_file.unlink()
                    else:
                        raise
            except Exception as e:
                logger.warning(f"Error checking lock file: {e}")
                # Remove potentially corrupted lock file
                self.lock_file.unlink()

        # Create lock file with current PID
        import os
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.lock_file, 'w') as f:
            f.write(str(os.getpid()))

        self.locked = True
        logger.info(f"Process lock acquired: {self.lock_file}")
        return True

    def release(self):
        """Release the lock."""
        if self.locked and self.lock_file.exists():
            try:
                self.lock_file.unlink()
                logger.info("Process lock released")
            except Exception as e:
                logger.warning(f"Error releasing lock: {e}")
        self.locked = False

    def __enter__(self):
        if not self.acquire():
            sys.exit(1)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
'''

def add_lock_to_file(filepath: str):
    """Add process lock mechanism to gdelt_collector.py"""

    with open(filepath, 'r') as f:
        content = f.read()

    # Check if already patched
    if 'class ProcessLock:' in content:
        print("✓ File already has ProcessLock - skipping")
        return

    # Find the GDELTCollector class definition
    lines = content.split('\n')
    insert_pos = None

    for i, line in enumerate(lines):
        if line.startswith('class GDELTCollector:'):
            insert_pos = i
            break

    if insert_pos is None:
        print("✗ Could not find GDELTCollector class definition")
        return

    # Insert ProcessLock class before GDELTCollector
    lock_lines = LOCK_MECHANISM.strip().split('\n')
    new_lines = lines[:insert_pos] + [''] + lock_lines + ['', ''] + lines[insert_pos:]

    # Now modify __init__ to add lock
    new_content = '\n'.join(new_lines)

    # Add lock to __init__
    init_addition = '''        # Process lock to prevent duplicate instances
        self._lock = None'''

    if 'self._lock = None' not in new_content:
        new_content = new_content.replace(
            'self.is_running = False  # For continuous mode',
            'self.is_running = False  # For continuous mode\n' + init_addition
        )

    # Modify run_continuous to use lock
    run_continuous_start = '''    def run_continuous(self, interval_minutes: int = 15):
        """
        Run collector continuously with periodic updates.

        Similar to trader.py pattern - runs indefinitely until stopped.

        Args:
            interval_minutes: Minutes between collection cycles (default: 15)
        """
        logger.info(f"Starting continuous GDELT collection (every {interval_minutes} min)")
        logger.info("Press Ctrl+C to stop gracefully")

        self.is_running = True'''

    run_continuous_with_lock = '''    def run_continuous(self, interval_minutes: int = 15):
        """
        Run collector continuously with periodic updates.

        Similar to trader.py pattern - runs indefinitely until stopped.

        Args:
            interval_minutes: Minutes between collection cycles (default: 15)
        """
        # Acquire process lock
        lock_file = Path(self.db_path).parent / 'gdelt_collector.lock'
        self._lock = ProcessLock(str(lock_file))

        if not self._lock.acquire():
            logger.error("Another instance is already running. Exiting.")
            return

        logger.info(f"Starting continuous GDELT collection (every {interval_minutes} min)")
        logger.info("Press Ctrl+C to stop gracefully")

        self.is_running = True'''

    new_content = new_content.replace(run_continuous_start, run_continuous_with_lock)

    # Modify stop() to release lock
    stop_method = '''    def stop(self):
        """Stop the continuous collector."""
        logger.info("Stopping GDELT collector...")
        self.is_running = False
        logger.info("GDELT collector stopped")'''

    stop_method_with_lock = '''    def stop(self):
        """Stop the continuous collector."""
        logger.info("Stopping GDELT collector...")
        self.is_running = False
        if self._lock:
            self._lock.release()
        logger.info("GDELT collector stopped")'''

    new_content = new_content.replace(stop_method, stop_method_with_lock)

    # Write back
    backup_path = filepath + '.before_lock'
    Path(filepath).rename(backup_path)
    print(f"✓ Backed up original to: {backup_path}")

    with open(filepath, 'w') as f:
        f.write(new_content)

    print(f"✓ Added ProcessLock to {filepath}")
    print("  - Prevents duplicate instances from running")
    print("  - Automatically cleans up stale lock files")
    print("  - Safe for production use")


if __name__ == '__main__':
    collector_path = 'gdelt_collector.py'

    if not Path(collector_path).exists():
        print(f"✗ Error: {collector_path} not found")
        sys.exit(1)

    print("=== Adding Process Lock to GDELT Collector ===\n")
    add_lock_to_file(collector_path)
    print("\n✓ Patch complete!")
