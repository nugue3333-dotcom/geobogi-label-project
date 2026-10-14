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
    """Preserve barcode payload exactly; validation belongs to the symbology.

    This is intentionally separate from command-language text sanitizers.
    Callers must encode as a bitmap or escape their command data boundary.
    """
    text = "" if value is None else str(value)
    if not text or not text.strip():
        raise ValueError("barcode is empty")
    if any(0xD800 <= ord(char) <= 0xDFFF for char in text):
        raise ValueError("barcode contains an invalid Unicode surrogate")
    return text


def _to_label_text(value: object, max_length: int = 48) -> str:
    text = "" if value is None else str(value).strip()
    text = " ".join(text.split())
    return text[:max_length]
