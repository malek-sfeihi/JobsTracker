import base64
import re
from datetime import datetime, timezone
from html import unescape

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.core.config import settings


class LoginRequiredError(Exception):
    """Raised when Google needs you to log in again but nobody is there to do it."""


def get_credentials(interactive: bool = True) -> Credentials:
    """Return valid Google credentials, logging in through the browser if needed.

    interactive=False (scheduled runs): never open a browser - raise LoginRequiredError instead,
    otherwise the task would wait forever for a login nobody is there to do.
    """
    creds = None
    if settings.token_path.exists():
        creds = Credentials.from_authorized_user_file(
            str(settings.token_path), settings.gmail_scopes
        )

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            # Refresh token expired or revoked (every 7 days while the app is in "Testing")
            creds = None

    if not creds or not creds.valid:
        if not interactive:
            raise LoginRequiredError(
                "Gmail login expired. Run `python -m app.services.sync` once by hand to log in again."
            )
        flow = InstalledAppFlow.from_client_secrets_file(
            str(settings.client_secret_path), settings.gmail_scopes
        )
        creds = flow.run_local_server(port=0)

    settings.token_path.write_text(creds.to_json())
    return creds


def get_gmail_service(interactive: bool = True):
    return build("gmail", "v1", credentials=get_credentials(interactive))


def _decode(data: str) -> str:
    # Gmail sends bodies as base64url, sometimes without the "=" padding
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _find_part(payload: dict, mime_type: str) -> str | None:
    """Search the email's tree of parts for the first one of the given type."""
    data = payload.get("body", {}).get("data")
    if payload.get("mimeType") == mime_type and data:
        return _decode(data)
    for part in payload.get("parts", []):
        found = _find_part(part, mime_type)
        if found:
            return found
    return None


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def extract_body(payload: dict) -> str:
    """Return the email body as plain text, converting from HTML if needed."""
    text = _find_part(payload, "text/plain")
    if text:
        return text
    html = _find_part(payload, "text/html")
    return _html_to_text(html) if html else ""


# On "too many requests" errors, wait and retry (1s, 2s, 4s, ...) instead of crashing
MAX_RETRIES = 8


def _fetch_email(service, message_id: str) -> dict:
    full = service.users().messages().get(
        userId="me", id=message_id, format="full"
    ).execute(num_retries=MAX_RETRIES)
    headers = {h["name"]: h["value"] for h in full["payload"]["headers"]}
    # internalDate = when Gmail received it, in milliseconds since 1970 (more reliable
    # than the "Date" header, whose format varies from sender to sender)
    received_at = datetime.fromtimestamp(int(full["internalDate"]) / 1000, tz=timezone.utc)
    return {
        "id": message_id,
        "thread_id": full["threadId"],
        "sender": headers.get("From", ""),
        "subject": headers.get("Subject", ""),
        "date": headers.get("Date", ""),
        "received_at": received_at.isoformat(),
        "body": extract_body(full["payload"]),
    }


def list_message_ids(query: str = "", max_results: int = 50, interactive: bool = True) -> list[str]:
    """Return the IDs of emails matching a Gmail search query (cheap: no content downloaded)."""
    service = get_gmail_service(interactive)

    message_ids = []
    page_token = None
    # Gmail returns results page by page, so we keep asking until we have enough
    while len(message_ids) < max_results:
        response = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=min(500, max_results - len(message_ids)),
            pageToken=page_token,
        ).execute(num_retries=MAX_RETRIES)
        message_ids += [m["id"] for m in response.get("messages", [])]
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return message_ids


def fetch_emails(message_ids: list[str], interactive: bool = True) -> list[dict]:
    """Download the full content of the given emails."""
    service = get_gmail_service(interactive)
    emails = []
    for i, message_id in enumerate(message_ids, start=1):
        emails.append(_fetch_email(service, message_id))
        if i % 25 == 0 or i == len(message_ids):
            print(f"Fetched {i}/{len(message_ids)} emails...")
    return emails


def search_emails(query: str = "", max_results: int = 50) -> list[dict]:
    """Return emails matching a Gmail search query (same syntax as the Gmail search bar)."""
    return fetch_emails(list_message_ids(query, max_results))


if __name__ == "__main__":
    for email in search_emails(max_results=10):
        print(f"{email['date']} | {email['sender']} | {email['subject']}")
