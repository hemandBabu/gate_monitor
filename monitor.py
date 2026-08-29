import hashlib
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from bs4 import BeautifulSoup

# ... other code ...

def get_cleaned_page_text(url: str) -> str:
    # Create a custom SSL context
    ctx = create_urllib3_context()
    ctx.options |= 0x4  # SSL_OP_LEGACY_SERVER_CONNECT
    
    # Create an adapter with the custom SSL context
    adapter = HTTPAdapter()
    adapter.init_poolmanager(ssl_context=ctx)
    
    session = requests.Session()
    session.mount('https://', adapter)
    
    try:
        response = session.get(
            url, 
            headers=HEADERS, 
            timeout=30
        )
    except requests.exceptions.SSLError:
        # Fallback: Disable SSL verification
        response = requests.get(
            url, 
            headers=HEADERS, 
            timeout=30, 
            verify=False
        )

    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "noscript", "svg", "meta"]):
        element.decompose()

    return " ".join(soup.stripped_strings)
