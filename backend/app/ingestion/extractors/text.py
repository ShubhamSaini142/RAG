"""Plain-text / markdown extractor."""


def extract(raw: bytes) -> list[dict]:
    """Decode raw bytes to text. Returns a list of {text, metadata} segments."""
    content = raw.decode("utf-8", errors="replace")
    return [{"text": content, "metadata": {}}]
