import imaplib
import email
from email.header import decode_header
import logging
from typing import List, Dict, Any
import html2text
import smtplib
import io
import PyPDF2
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger("CAKRA_ZIMBRA_SERVICE")

def get_text_from_email(msg):
    text_content = ""
    html_content = ""
    attachments_text = ""
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            
            # Handling attachments
            if "attachment" in content_disposition:
                filename = part.get_filename()
                if filename and filename.lower().endswith(".pdf"):
                    try:
                        pdf_bytes = part.get_payload(decode=True)
                        if pdf_bytes:
                            reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
                            pdf_text = f"\n\n--- LAMPIRAN: {filename} ---\n"
                            for page in reader.pages:
                                pdf_text += page.extract_text() + "\n"
                            attachments_text += pdf_text
                    except Exception as e:
                        logger.warning(f"Failed to read PDF attachment {filename}: {e}")
                elif filename and filename.lower().endswith(".txt"):
                    try:
                        txt_bytes = part.get_payload(decode=True)
                        if txt_bytes:
                            attachments_text += f"\n\n--- LAMPIRAN: {filename} ---\n" + txt_bytes.decode('utf-8', errors='ignore')
                    except Exception as e:
                        pass
                continue
            
            try:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or 'utf-8'
                    decoded = payload.decode(charset, errors='ignore')
                    if content_type == "text/plain":
                        text_content += decoded
                    elif content_type == "text/html":
                        html_content += decoded
            except Exception as e:
                logger.warning(f"Failed to decode email part: {e}")
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or 'utf-8'
                decoded = payload.decode(charset, errors='ignore')
                if msg.get_content_type() == "text/plain":
                    text_content = decoded
                elif msg.get_content_type() == "text/html":
                    html_content = decoded
        except Exception as e:
            logger.warning(f"Failed to decode single email: {e}")
            
    text_res = ""
    html_res = ""
    
    if text_content.strip():
        text_res = text_content.strip()
    elif html_content.strip():
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True # Cegah base64 image meledakkan token LLM
        text_res = h.handle(html_content).strip()
    else:
        text_res = "[Konten tidak dapat dibaca]"
        
    text_res += attachments_text
        
    if html_content.strip():
        html_res = html_content.strip()
    else:
        html_res = f"<div>{text_res.replace(chr(10), '<br>')}</div>"
        
    return text_res, html_res

def decode_mime_header(header_value):
    if not header_value:
        return ""
    try:
        # Pindad emails sometimes have broken encoding boundaries like ?==?UTF-8?
        header_value = str(header_value).replace("?==?UTF-8?", "?= =?UTF-8?")
        decoded_fragments = decode_header(header_value)
        result = ""
        for frag, encoding in decoded_fragments:
            if isinstance(frag, bytes):
                result += frag.decode(encoding or 'utf-8', errors='ignore')
            else:
                result += frag
        return result
    except Exception as e:
        logger.warning(f"Failed to decode header {header_value}: {e}")
        return str(header_value)

def fetch_unread_emails(email_address: str, password: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Koneksi ke IMAP mail.pindad.com dan tarik email terbaru.
    """
    if password == "MOCK_TEST":
        import datetime
        logger.info(f"[ZIMBRA] Returning MOCK emails for {email_address}...")
        now_str = datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0700")
        return [
            {
                "id": "mock-1",
                "sender": "John Doe <johndoe@pindad.com>",
                "cc": "",
                "subject": "Penawaran Vendor A",
                "content": "Halo, ini adalah penawaran vendor A dengan harga Rp 500.000.000. Mohon segera di-review.",
                "content_html": "<p>Halo, ini adalah penawaran vendor A dengan harga Rp 500.000.000. Mohon segera di-review.</p>",
                "received_at": now_str,
                "priority": "🔴 Unread"
            },
            {
                "id": "mock-2",
                "sender": "Spammer <spam@scam.com>",
                "cc": "",
                "subject": "YOU WON $1,000,000",
                "content": "Click here to claim your prize! Please send your password and credit card number to receive your funds immediately.",
                "content_html": "<p>Click here to claim your prize! Please send your password and credit card number to receive your funds immediately.</p>",
                "received_at": now_str,
                "priority": "🔴 Unread"
            }
        ]

    imap_host = "mail.pindad.com"
    imap_port = 993
    
    logger.info(f"[ZIMBRA] Connecting to {imap_host}:{imap_port} for {email_address}...")
    
    try:
        mail = imaplib.IMAP4_SSL(imap_host, imap_port)
        mail.login(email_address, password)
        
        mail.select("inbox")
        
        # Cari email (bisa UNSEEN atau ALL). Kita ambil ALL tapi batasi jumlahnya saja agar ada data.
        status, data = mail.search(None, "ALL")
        if status != "OK":
            logger.error(f"[ZIMBRA] Failed to search inbox: {status}")
            return []
            
        email_ids = data[0].split()
        
        if not email_ids:
            return []
            
        # Ambil `limit` email terakhir
        latest_email_ids = email_ids[-limit:]
        
        results = []
        for e_id in reversed(latest_email_ids):
            status, msg_data = mail.fetch(e_id, "(RFC822)")
            if status != "OK":
                continue
                
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    subject = decode_mime_header(msg.get("Subject"))
                    sender = decode_mime_header(msg.get("From"))
                    cc = decode_mime_header(msg.get("Cc"))
                    date = msg.get("Date")
                    
                    content_text, content_html = get_text_from_email(msg)
                    
                    results.append({
                        "id": e_id.decode("utf-8"),
                        "sender": sender,
                        "cc": cc,
                        "subject": subject,
                        "content": content_text, # Untuk LLM
                        "content_html": content_html, # Untuk UI render
                        "received_at": date,
                        "priority": "🔴 Unread" if "UNSEEN" in str(mail.fetch(e_id, "(FLAGS)")[1]) else "🟢 Read"
                    })
                    
        mail.logout()
        logger.info(f"[ZIMBRA] Successfully fetched {len(results)} emails.")
        return results
        
    except imaplib.IMAP4.error as e:
        logger.error(f"[ZIMBRA] IMAP Login Error: {e}")
        raise ValueError(f"Autentikasi IMAP gagal: {e}")
    except Exception as e:
        logger.error(f"[ZIMBRA] Unexpected error: {e}")
        raise Exception(f"Gagal mengambil email: {e}")

def send_email_reply(email_address: str, password: str, to_address: str, subject: str, body: str, cc_address: str = None) -> bool:
    """Mengirim balasan email menggunakan SMTP Zimbra."""
    if password == "MOCK_TEST":
        logger.info(f"[ZIMBRA] MOCK: Email sent successfully to {to_address}")
        return True

    smtp_host = "mail.pindad.com"
    
    msg = MIMEMultipart()
    msg['From'] = email_address
    msg['To'] = to_address
    if cc_address:
        msg['Cc'] = cc_address
    
    # Prepend Re: if not present, and preserve Fwd:
    subj_lower = subject.lower()
    if not subj_lower.startswith("re:") and not subj_lower.startswith("fwd:") and not subj_lower.startswith("fw:"):
        msg['Subject'] = f"Re: {subject}"
    else:
        msg['Subject'] = subject
        
    msg.attach(MIMEText(body, 'plain'))
    
    destinations = [to_address]
    if cc_address:
        destinations.extend([c.strip() for c in cc_address.split(",") if c.strip()])
    
    try:
        # Coba port 465 (SSL)
        server = smtplib.SMTP_SSL(smtp_host, 465)
        server.login(email_address, password)
        server.send_message(msg, from_addr=email_address, to_addrs=destinations)
        server.quit()
        logger.info(f"[ZIMBRA] Email sent successfully to {to_address} via 465")
        return True
    except Exception as e:
        logger.warning(f"[ZIMBRA] 465 failed, trying 587: {e}")
        try:
            # Fallback port 587 (TLS)
            server = smtplib.SMTP(smtp_host, 587)
            server.starttls()
            server.login(email_address, password)
            server.send_message(msg, from_addr=email_address, to_addrs=destinations)
            server.quit()
            logger.info(f"[ZIMBRA] Email sent successfully to {to_address} via 587")
            return True
        except Exception as e2:
            logger.error(f"[ZIMBRA] Failed to send email completely: {e2}")
            raise Exception(f"Gagal mengirim email: {e2}")
