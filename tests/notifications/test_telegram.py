from __future__ import annotations

import pytest

from openfreela.notifications.telegram import (
    TelegramNotifier,
    validate_telegram_response,
)


def test_telegram_notifier_builds_send_message_url() -> None:
    notifier = TelegramNotifier("TOKEN", "CHAT")

    assert (
        notifier.send_message_url() == "https://api.telegram.org/botTOKEN/sendMessage"
    )


def test_validate_telegram_response_accepts_ok_true() -> None:
    validate_telegram_response({"ok": True})


def test_validate_telegram_response_rejects_error() -> None:
    with pytest.raises(ValueError, match="Telegram rejected"):
        validate_telegram_response({"ok": False})
