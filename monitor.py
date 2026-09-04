import hashlib
import os
import re
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup

TARGET_URL = "https://exams.nta.nic.in/swayam/"
STATE_FILE = "last_hash.txt"

# Read environment variables set by GitHub Actions
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "").strip()
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "").strip()
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "").strip()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def create_legacy_ssl_context() -> ssl.SSLContext:
    """Handles older government server TLS configs and OpenSSL 3 renegotiation."""
    ctx = ssl.create_default_context()
    ctx.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def check_for_swayam_announcement(url: str) -> tuple[bool, str]:
    """
    Fetches the portal HTML, strips tags/scripts, filters lines mentioning SWAYAM,
    and checks for July 2026 registration/exam announcements.
    """
    ctx = create_legacy_ssl_context()
    req = Request(url, headers=HEADERS)

    with urlopen(req, context=ctx, timeout=30) as response:
        html_content = response.read().decode("utf-8", errors="ignore")

    soup = BeautifulSoup(html_content, "html.parser")
    for element in soup(["script", "style", "noscript", "svg", "meta"]):
        element.decompose()

    # Extract clean text chunks
    strings = [s.strip() for s in soup.stripped_strings if s.strip()]

    # Filter lines mentioning SWAYAM
    swayam_lines = [line for line in strings if "swayam" in line.lower()]

    # Pattern: July + 2026 + (registration/exam/application/course)
    pattern = re.compile(
        r"(?=.*july)(?=.*2026)(?=.*(registration|exam|application|courses?))",
        re.IGNORECASE,
    )

    matching_snippets = [line for line in swayam_lines if pattern.search(line)]

    if matching_snippets:
        combined_snippets = "\n".join(f"- {s}" for s in set(matching_snippets))
        return True, combined_snippets

    return False, ""


def send_email_alert(detected_content: str, content_hash: str):
    if not (SENDER_EMAIL and SENDER_PASSWORD and RECIPIENT_EMAIL):
        print("Notice: Email secrets missing. Skipping email dispatch.")
        return

    subject = "🚨 SWAYAM July 2026 Courses Exam Registration Detected!"
    body = f"""Hello,

An announcement matching SWAYAM July 2026 exam registration was detected on the official NTA SWAYAM portal:
{TARGET_URL}

Matched Details:
{detected_content}

Notification Hash: {content_hash}
"""
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        print("Notification email sent successfully.")
    except Exception as e:
        print(f"Warning: Failed to send email: {e}")


def main():
    found, snippet = check_for_swayam_announcement(TARGET_URL)

    if not found:
        print("No SWAYAM July 2026 exam registration announcement detected.")
        return

    # Compute hash of the matched content to avoid alert spam on subsequent runs
    current_hash = hashlib.sha256(snippet.encode("utf-8")).hexdigest()

    old_hash = ""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            old_hash = f.read().strip()

    if current_hash != old_hash:
        print(f"Target announcement found! (Hash: {current_hash[:8]})")
        send_email_alert(snippet, current_hash)
        with open(STATE_FILE, "w") as f:
            f.write(current_hash)
    else:
        print("Announcement still present, but already notified. Skipping email.")


if __name__ == "__main__":
    main()
