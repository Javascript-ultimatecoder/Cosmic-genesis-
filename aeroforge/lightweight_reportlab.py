class Paragraph:
    def __init__(self, text, style):
        self.text = text


class Spacer:
    def __init__(self, *_):
        pass


class SimpleDocTemplate:
    def __init__(self, path):
        self.path = path

    def build(self, story):
        lines = []
        for item in story:
            if hasattr(item, "text"):
                lines.append(item.text)
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


def getSampleStyleSheet():
    return {"Heading2": object(), "BodyText": object()}
