def test_builds_callback_with_message_id():
    from mnemosyne.hermes.telegram_callbacks import build_callback_data, parse_callback_data

    data = build_callback_data(action="dismiss", message_id="msg-123", value="disc-9")
    parsed = parse_callback_data(data)

    assert parsed["action"] == "dismiss"
    assert parsed["message_id"] == "msg-123"
    assert parsed["value"] == "disc-9"


def test_parse_callback_rejects_invalid_format():
    from mnemosyne.hermes.telegram_callbacks import parse_callback_data

    assert parse_callback_data("bad") is None
    assert parse_callback_data("action:missing") is None

