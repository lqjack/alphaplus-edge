import logging
import inspect
import threading

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from core.tools.files import get_file_content_type

logger = logging.getLogger(__name__)


def _default_on_created_callback(file_path, account_id):
    from api.rest.services.scheduled_task import process_file_async

    process_file_async(file_path=file_path, user_id=account_id)


class DirectoryMonitor:
    def __init__(self, path, account_id, on_created_callback=None):
        self.path = path
        self.account_id = account_id
        if not on_created_callback:
            on_created_callback = _default_on_created_callback
        self.on_created_callback = on_created_callback
        self.observer = None
        self.event_handler = FileChangeHandler(self.on_created_callback, self.account_id, path)

    def start(self):
        self.observer = Observer()
        self.observer.schedule(self.event_handler, self.path, recursive=True)
        self.observer.start()
        logger.info(f"Monitoring started for path: {self.path}")

    def stop(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
        logger.info(f"Monitoring stopped for path: {self.path}")

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, on_created_callback, account_id, path):
        self.on_created_callback = on_created_callback
        self.account_id = account_id
        self.path = path

    def _build_callback_args(self, file_path):
        default_args = (file_path, self.account_id, self.path, "file")

        try:
            parameters = list(inspect.signature(self.on_created_callback).parameters.values())
        except (TypeError, ValueError):
            return default_args

        if any(param.kind == inspect.Parameter.VAR_POSITIONAL for param in parameters):
            return default_args

        positional_params = [
            param
            for param in parameters
            if param.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        supported_arg_count = max(1, min(len(positional_params), len(default_args)))
        return default_args[:supported_arg_count]

    def on_created(self, event):
        if event.is_directory:
            return
        file_path = event.src_path

        content_type = get_file_content_type(file_path)

        if not content_type:
            return

        callback_args = self._build_callback_args(file_path)
        threading.Thread(target=self.on_created_callback, args=callback_args).start()
