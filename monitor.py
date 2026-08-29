import hashlib
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context


class LegacySSLAdapter(HTTPAdapter):
    """Custom adapter enabling OpenSSL 3 legacy renegotiation for legacy servers."""

    def __init__(self, *args, **kwargs):
        self.ssl_context = create_urllib3_context()
        # Enable SSL_OP_LEGACY_SERVER_CONNECT (0x4)
        self.ssl_context.options |= 0x4
        # Disable strict hostname/cert validation if server cert chains are broken
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        pool_kwargs["ssl_context"] = self.ssl_context
        return super().init_poolmanager(
            connections, maxsize, block=block, **pool_kwargs
        )


def get_cleaned_page_text(url: str) -> str:
    session = requests.Session()
    session.mount("https://", LegacySSLAdapter())

    response = session.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "noscript", "svg", "meta"]):
        element.decompose()

    return " ".join(soup.stripped_strings)
