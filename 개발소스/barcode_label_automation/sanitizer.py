from __future__ import annotations


def sanitize_slcs_text(value: object) -> str:
    text = _to_label_text(value)
    return text.replace("'", " ")


def sanitize_tspl_text(value: object) -> str:
    text = _to_label_text(value)
    return text.replace('"', " ")


def sanitize_zpl_text(value: object) -> str:
    text = _to_label_text(value)
    return text.replace("^", " ").replace("~", " ")


def sanitize_barcode(value: object) -> str:
    text = _to_label_text(value)
    allowed = []
    for char in text:
        if char.isalnum() or char in "-_./":
            allowed.append(char)
    sanitized = "".join(allowed)
    if not sanitized:
        raise ValueError("barcode is empty after sanitization")
    return sanitized


def _to_label_text(value: object, max_length: int = 48) -> str:
    text = "" if value is None else str(value).strip()
    text = " ".join(text.split())
    return text[:max_length]
