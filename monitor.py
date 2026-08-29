import hashlib
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

TARGET_URL = "https://gate2027.iitm.ac.in"
HASH_FILE = "last_hash.txt"

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


# Custom SSL Adapter to allow OpenSSL 3 legacy renegotiation for IIT servers
class LegacySSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        # 0x4 corresponds to ssl.OP_LEGACY_SERVER_CONNECT
        ctx.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def get_cleaned_page_text(url: str) -> str:
    session = requests.Session()
    session.mount("https://", LegacySSLAdapter())

    response = session.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "noscript", "svg", "meta"]):
        element.decompose()

    return " ".join(soup.stripped_strings)


def send_email_alert(new_hash: str):
    if not (SENDER_EMAIL and SENDER_PASSWORD and RECIPIENT_EMAIL):
        print("Skipping email: Missing email credentials in secrets.")
        return

    subject = "🚨 GATE 2027 Portal Update Detected!"
    body = f"""Hello,

A change has been detected on the GATE 2027 website:
{TARGET_URL}

Check the portal to see if the registration/application dates have opened.

New Hash: {new_hash}
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
        print(f"Warning: Failed to send email alert: {e}")


def main():
    cleaned_content = get_cleaned_page_text(TARGET_URL)
    current_hash = hashlib.sha256(cleaned_content.encode("utf-8")).hexdigest()

    old_hash = ""
    if os.path.exists(HASH_FILE):
        with open(HASH_FILE, "r") as f:
            old_hash = f.read().strip()

    if not old_hash:
        print(f"First run: Initializing baseline hash ({current_hash[:8]}).")
        with open(HASH_FILE, "w") as f:
            f.write(current_hash)
    elif current_hash != old_hash:
        print(f"Change detected! (Old: {old_hash[:8]} -> New: {current_hash[:8]})")
        send_email_alert(current_hash)
        with open(HASH_FILE, "w") as f:
            f.write(current_hash)
    else:
        print("No changes found on the page.")


if __name__ == "__main__":
    main()
