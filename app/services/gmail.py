from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.core.config import settings


def get_credentials() -> Credentials:
    """Return valid Google credentials, logging in through the browser if needed."""
    creds = None
    if settings.token_path.exists():
        creds = Credentials.from_authorized_user_file(
            str(settings.token_path), settings.gmail_scopes
        )

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(settings.client_secret_path), settings.gmail_scopes
        )
        creds = flow.run_local_server(port=0)

    settings.token_path.write_text(creds.to_json())
    return creds


def get_gmail_service():
    return build("gmail", "v1", credentials=get_credentials())


def list_recent_emails(max_results: int = 10) -> list[dict]:
    """Return the most recent emails as dicts with id, sender, subject and date."""
    service = get_gmail_service()
    response = service.users().messages().list(userId="me", maxResults=max_results).execute()

    emails = []
    for message in response.get("messages", []):
        full = service.users().messages().get(
            userId="me",
            id=message["id"],
            format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        ).execute()
        headers = {h["name"]: h["value"] for h in full["payload"]["headers"]}
        emails.append({
            "id": message["id"],
            "sender": headers.get("From", ""),
            "subject": headers.get("Subject", ""),
            "date": headers.get("Date", ""),
        })
    return emails


if __name__ == "__main__":
    for email in list_recent_emails():
        print(f"{email['date']} | {email['sender']} | {email['subject']}")
