from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class TelegramNotifier:
    """Telegram Bot API notifier.

    Example:
        notifier = TelegramNotifier("token", "chat")
    """

    bot_token: str
    chat_id: str
    timeout_seconds: int = 30

    def send_message(self, text: str) -> None:
        """Send one Telegram message.

        Example:
            notifier.send_message("Project matched")
        """
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
        post_form(self.send_message_url(), payload, self.timeout_seconds)

    def send_message_url(self) -> str:
        """Return the Telegram sendMessage endpoint URL.

        Example:
            url = notifier.send_message_url()
        """
        return f"https://api.telegram.org/bot{self.bot_token}/sendMessage"


def post_form(url: str, payload: dict[str, str], timeout_seconds: int) -> None:
    """Post form data and validate Telegram's JSON response.

    Example:
        post_form("https://api.telegram.org/botTOKEN/sendMessage", {}, 10)
    """
    request = Request(url, data=urlencode(payload).encode("utf-8"))
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except URLError as error:
        raise ConnectionError("Could not send Telegram notification.") from error
    validate_telegram_response(decoded)


def validate_telegram_response(response: object) -> None:
    """Raise when Telegram did not accept the message.

    Example:
        validate_telegram_response({"ok": True})
    """
    if isinstance(response, dict) and response.get("ok") is True:
        return
    message = f"Telegram rejected notification; expected ok=true, got {response!r}."
    raise ValueError(message)
