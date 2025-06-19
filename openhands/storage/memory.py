import os

from openhands.core.logger import openhands_logger as logger
from openhands.storage.files import FileStore


class InMemoryFileStore(FileStore):
    files: dict[str, str]

    def __init__(self, files: dict[str, str] | None = None) -> None:
        self.files = {}
        if files is not None:
            self.files = files

    def write(self, path: str, contents: str | bytes) -> None:
        if isinstance(contents, bytes):
            contents = contents.decode('utf-8')
        self.files[path] = contents

    def read(self, path: str) -> str:
        if path not in self.files:
            # Auto-create metadata.json with default content if missing
            if path.endswith('metadata.json'):
                logger.info(f"Auto-creating missing metadata file: {path}")
                # Extract conversation_id from path: sessions/{conversation_id}/metadata.json
                parts = path.split('/')
                if len(parts) >= 2:
                    conversation_id = parts[-2]
                    default_metadata = {
                        "conversation_id": conversation_id,
                        "title": f"Conversation {conversation_id[:8]}",
                        "trigger": "gui",
                        "user_id": None,
                        "selected_repository": None,
                        "selected_branch": None,
                        "git_provider": None,
                        "llm_model": "openrouter/anthropic/claude-3.5-sonnet",
                        "created_at": "2024-01-01T00:00:00Z",
                        "updated_at": "2024-01-01T00:00:00Z"
                    }
                    import json
                    self.files[path] = json.dumps(default_metadata)
                    return self.files[path]
            raise FileNotFoundError(path)
        return self.files[path]

    def list(self, path: str) -> list[str]:
        files = []
        for file in self.files:
            if not file.startswith(path):
                continue
            suffix = file.removeprefix(path)
            parts = suffix.split('/')
            if parts[0] == '':
                parts.pop(0)
            if len(parts) == 1:
                files.append(file)
            else:
                dir_path = os.path.join(path, parts[0])
                if not dir_path.endswith('/'):
                    dir_path += '/'
                if dir_path not in files:
                    files.append(dir_path)
        return files

    def delete(self, path: str) -> None:
        try:
            keys_to_delete = [key for key in self.files.keys() if key.startswith(path)]
            for key in keys_to_delete:
                del self.files[key]
            logger.debug(f'Cleared in-memory file store: {path}')
        except Exception as e:
            logger.error(f'Error clearing in-memory file store: {str(e)}')
