from dataclasses import dataclass
from typing import Any, Callable


class FastAPI:
    def __init__(self, title: str = "App", version: str = "0.1"):
        self.title = title
        self.version = version
        self.routes = []

    def get(self, path: str):
        def decorator(func: Callable):
            self.routes.append(("GET", path, func.__name__))
            return func
        return decorator

    def post(self, path: str):
        def decorator(func: Callable):
            self.routes.append(("POST", path, func.__name__))
            return func
        return decorator


@dataclass
class UploadFile:
    filename: str = ""
    content: bytes = b""

    async def read(self) -> bytes:
        return self.content


def File(default: Any = None):
    return default


def Form(default: Any = None):
    return default
