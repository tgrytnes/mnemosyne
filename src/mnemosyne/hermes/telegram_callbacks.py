from __future__ import annotations


def build_callback_data(*, action: str, message_id: str, value: str) -> str:
    return f"{action}:{message_id}:{value}"


def parse_callback_data(data: str) -> dict | None:
    parts = data.split(":", 2)
    if len(parts) != 3:
        return None
    action, message_id, value = parts
    if not action or not message_id:
        return None
    return {"action": action, "message_id": message_id, "value": value}
