"""File watcher for live re-indexing."""
import os
import time
import threading
from codegraph.repo_scanner import scan_repository
from codegraph.graph_builder import insert_into_falkordb

_debounce_sec = 2.0
_last_event = 0
_timer = None
_lock = threading.Lock()


def _reindex(path):
    print("Re-indexing...")
    entities = scan_repository(path)
    insert_into_falkordb(path, entities)
    print(f"Done. {len(entities['files'])} files, {len(entities['classes'])} classes.")


def _schedule_reindex(path):
    global _timer, _last_event
    with _lock:
        _last_event = time.time()
        if _timer:
            _timer.cancel()
        _timer = threading.Timer(_debounce_sec, _do_reindex, args=[path])
        _timer.start()


def _do_reindex(path):
    global _timer
    with _lock:
        _timer = None
    _reindex(path)


def watch_and_index(path):
    """Watch directory and re-index on file changes."""
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        print("Install watchdog: pip install watchdog")
        return
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        print("Path must be a directory")
        return
    print(f"Watching {path}. Initial index...")
    _reindex(path)
    print("Watching for changes. Ctrl+C to stop.")

    class Handler(FileSystemEventHandler):
        def on_any_event(self, event):
            if event.is_directory:
                return
            src = getattr(event, "src_path", "") or ""
            if any(x in src for x in (".git", "__pycache__", "node_modules", ".venv")):
                return
            if src.endswith((".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".c", ".cpp", ".h", ".cs")):
                _schedule_reindex(path)

    observer = Observer()
    observer.schedule(Handler(), path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
