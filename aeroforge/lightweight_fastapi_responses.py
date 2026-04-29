class HTMLResponse:
    def __init__(self, content: str):
        self.content = content


class FileResponse:
    def __init__(self, path: str, filename: str | None = None):
        self.path = path
        self.filename = filename
