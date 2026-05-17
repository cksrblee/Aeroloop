import uuid

def make_id(prefix: str) -> str:
    """
    Generates a unique ID with the given prefix.
    """
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"
