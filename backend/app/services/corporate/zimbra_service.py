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

def _select_imap_folder(mail: imaplib.IMAP4_SSL, folder: str) -> str:
    """Memilih folder IMAP yang tepat, dengan fallback untuk variasi nama folder Zimbra."""
    folder_lower = folder.strip().lower()
    if folder_lower in ["sent", "sent items", "terkirim", "sent messages"]:
        for candidate in ["Sent", "Sent Items", "Sent Messages", "INBOX.Sent"]:
            try:
                res, _ = mail.select(f'"{candidate}"' if " " in candidate else candidate)
                if res == "OK":
                    return candidate
            except Exception:
                continue
        # Fallback: cari dari list folder IMAP
        try:
            res, folder_list = mail.list()
            if res == "OK":
                for f_info in folder_list:
                    f_str = f_info.decode('utf-8', errors='ignore') if isinstance(f_info, bytes) else str(f_info)
                    if "sent" in f_str.lower():
                        folder_name = f_str.split(' "/" ')[-1].strip().strip('"')
                        res_sel, _ = mail.select(f'"{folder_name}"' if " " in folder_name else folder_name)
                        if res_sel == "OK":
                            return folder_name
        except Exception as e:
            logger.warning(f"[ZIMBRA] Failed to inspect IMAP folders for sent: {e}")
        return "Sent"
    elif folder_lower in ["drafts", "draft", "draf"]:
        for candidate in ["Drafts", "Draft", "INBOX.Drafts", "DRAFTS"]:
            try:
                res, _ = mail.select(f'"{candidate}"' if " " in candidate else candidate)
                if res == "OK":
                    return candidate
            except Exception:
                continue
        try:
            res, folder_list = mail.list()
            if res == "OK":
                for f_info in folder_list:
                    f_str = f_info.decode('utf-8', errors='ignore') if isinstance(f_info, bytes) else str(f_info)
                    if "draft" in f_str.lower():
                        folder_name = f_str.split(' "/" ')[-1].strip().strip('"')
                        res_sel, _ = mail.select(f'"{folder_name}"' if " " in folder_name else folder_name)
                        if res_sel == "OK":
                            return folder_name
        except Exception as e:
            logger.warning(f"[ZIMBRA] Failed to inspect IMAP folders for drafts: {e}")
        return "Drafts"
    else:
        mail.select("INBOX")
        return "INBOX"

def get_text_from_email(msg):
    text_content = ""
    html_content = ""
    attachments_text = ""
    attachments = []
    part_counter = 0

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition") or "")
            raw_filename = part.get_filename()
            
            # Deteksi apakah part adalah file lampiran
            is_attachment = "attachment" in content_disposition.lower() or bool(raw_filename)
            
            if is_attachment:
                filename = decode_mime_header(raw_filename) if raw_filename else f"lampiran_{part_counter}"
                try:
                    payload_bytes = part.get_payload(decode=True)
                    size_bytes = len(payload_bytes) if payload_bytes else 0
                    size_kb = round(size_bytes / 1024, 1)
                except Exception:
                    payload_bytes = None
                    size_kb = 0.0

                attachments.append({
                    "part_index": part_counter,
                    "filename": filename,
                    "content_type": content_type,
                    "size_kb": size_kb
                })

                # Jika PDF atau TXT, ekstrak teksnya untuk LLM context
                if payload_bytes:
                    fn_lower = filename.lower()
                    if fn_lower.endswith(".pdf"):
                        try:
                            reader = PyPDF2.PdfReader(io.BytesIO(payload_bytes))
                            pdf_text = f"\n\n--- LAMPIRAN: {filename} ---\n"
                            for page in reader.pages:
                                pdf_text += (page.extract_text() or "") + "\n"
                            attachments_text += pdf_text
                        except Exception as e:
                            logger.warning(f"Failed to read PDF attachment {filename}: {e}")
                    elif fn_lower.endswith(".txt"):
                        try:
                            attachments_text += f"\n\n--- LAMPIRAN: {filename} ---\n" + payload_bytes.decode('utf-8', errors='ignore')
                        except Exception:
                            pass

                part_counter += 1
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
            part_counter += 1
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
        
    return text_res, html_res, attachments

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

def fetch_unread_emails(email_address: str, password: str, limit: int = 10, folder: str = "inbox") -> List[Dict[str, Any]]:
    """
    Koneksi ke IMAP mail.pindad.com dan tarik email terbaru menggunakan IMAP UID permanen.
    Mendukung folder 'inbox' dan 'sent'.
    """
    imap_host = "mail.pindad.com"
    imap_port = 993
    
    logger.info(f"[ZIMBRA] Connecting to {imap_host}:{imap_port} for {email_address} (folder={folder})...")
    
    try:
        mail = imaplib.IMAP4_SSL(imap_host, imap_port)
        mail.login(email_address, password)
        
        selected_folder = _select_imap_folder(mail, folder)
        logger.info(f"[ZIMBRA] Selected mailbox folder: {selected_folder}")
        
        # Cari email menggunakan UID permanen
        status, data = mail.uid("search", None, "ALL")
        if status != "OK":
            logger.error(f"[ZIMBRA] Failed to search mailbox: {status}")
            return []
            
        email_uids = data[0].split()
        if not email_uids:
            mail.logout()
            return []
            
        # Ambil `limit` email terakhir
        latest_email_uids = email_uids[-limit:]
        
        results = []
        for uid in reversed(latest_email_uids):
            uid_str = uid.decode("utf-8")
            status, msg_data = mail.uid("fetch", uid, "(RFC822 FLAGS)")
            if status != "OK" or not msg_data:
                continue
                
            flags_str = ""
            msg = None
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                elif isinstance(response_part, bytes):
                    flags_str += response_part.decode('utf-8', errors='ignore')
            
            if not msg:
                continue
                
            subject = decode_mime_header(msg.get("Subject")) or "(Tanpa Subjek)"
            sender = decode_mime_header(msg.get("From")) or ""
            recipient = decode_mime_header(msg.get("To")) or ""
            cc = decode_mime_header(msg.get("Cc")) or ""
            date = msg.get("Date") or ""
            
            raw_msg_id = msg.get("Message-ID") or ""
            clean_msg_id = raw_msg_id.strip().strip("<>").strip()
            if not clean_msg_id:
                clean_msg_id = f"uid_{uid_str}_{email_address}"
                
            content_text, content_html, attachments = get_text_from_email(msg)
            
            # Tentukan prioritas dasar
            if folder.lower() in ["sent", "sent items", "terkirim"]:
                priority = "📤 Sent"
            else:
                is_read = ("\\seen" in flags_str.lower())
                priority = "🟢 Read" if is_read else "🔴 Unread"
                
            results.append({
                "id": uid_str,
                "uid": uid_str,
                "message_id": clean_msg_id,
                "sender": sender,
                "recipient": recipient,
                "cc": cc,
                "subject": subject,
                "content": content_text, # Untuk LLM
                "content_html": content_html, # Untuk UI render
                "received_at": date,
                "priority": priority,
                "folder": folder,
                "attachments": attachments
            })
                    
        mail.logout()
        logger.info(f"[ZIMBRA] Successfully fetched {len(results)} emails from {selected_folder}.")
        return results
        
    except imaplib.IMAP4.error as e:
        logger.error(f"[ZIMBRA] IMAP Login Error: {e}")
        raise ValueError(f"Autentikasi IMAP gagal: {e}")
    except Exception as e:
        logger.error(f"[ZIMBRA] Unexpected error: {e}")
        raise Exception(f"Gagal mengambil email: {e}")

def get_email_attachment_bytes(
    email_address: str, 
    password: str, 
    uid: str, 
    part_index: int, 
    folder: str = "inbox"
) -> Dict[str, Any]:
    """
    Mengambil file bytes lampiran asli secara on-demand berdasarkan UID dan part_index.
    """
    imap_host = "mail.pindad.com"
    imap_port = 993
    
    mail = imaplib.IMAP4_SSL(imap_host, imap_port)
    try:
        mail.login(email_address, password)
        _select_imap_folder(mail, folder)
        
        status, msg_data = mail.uid("fetch", uid.encode('utf-8'), "(RFC822)")
        if status != "OK" or not msg_data:
            raise ValueError(f"Email UID {uid} tidak ditemukan di IMAP")
            
        msg = None
        for part in msg_data:
            if isinstance(part, tuple):
                msg = email.message_from_bytes(part[1])
                break
                
        if not msg:
            raise ValueError("Gagal membaca pesan email")
            
        part_counter = 0
        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition") or "")
            raw_filename = part.get_filename()
            is_attachment = "attachment" in content_disposition.lower() or bool(raw_filename)
            
            if is_attachment:
                if part_counter == part_index:
                    filename = decode_mime_header(raw_filename) if raw_filename else f"lampiran_{part_index}"
                    content_type = part.get_content_type() or "application/octet-stream"
                    payload_bytes = part.get_payload(decode=True)
                    return {
                        "filename": filename,
                        "content_type": content_type,
                        "data": payload_bytes or b""
                    }
                part_counter += 1
                
        raise ValueError(f"Lampiran index {part_index} tidak ditemukan pada email")
    finally:
        try:
            mail.logout()
        except Exception:
            pass

def send_email_reply(
    email_address: str, 
    password: str, 
    to_address: str, 
    subject: str, 
    body: str, 
    cc_address: str = None,
    is_reply: bool = True,
    attachments: list = None
) -> bool:
    """Mengirim email (balasan maupun pesan baru) menggunakan SMTP Zimbra."""
    smtp_host = "mail.pindad.com"
    
    msg = MIMEMultipart()
    msg['From'] = email_address
    msg['To'] = to_address
    if cc_address:
        msg['Cc'] = cc_address
    
    # Prepend Re: hanya jika is_reply bernilai True
    if is_reply:
        subj_lower = subject.lower()
        if not subj_lower.startswith("re:") and not subj_lower.startswith("fwd:") and not subj_lower.startswith("fw:"):
            msg['Subject'] = f"Re: {subject}"
        else:
            msg['Subject'] = subject
    else:
        msg['Subject'] = subject
        
    try:
        import markdown
        import re
        
        # Pre-process body to fix common LLM markdown formatting issues
        # 1. Ensure blank line before list items
        processed_body = re.sub(r'([^\n])\n(\s*[\*\-]\s)', r'\1\n\n\2', body)
        # 2. Unescape blockquotes if the LLM escaped them (e.g. \>)
        processed_body = processed_body.replace('\\>', '>')
        
        raw_html = markdown.markdown(processed_body)
        
        # Bungkus dengan styling CSS dasar agar rapi di email client
        html_body = f"""
        <html>
        <head>
        <style>
            body {{ font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #333; }}
            ul, ol {{ margin-top: 5px; margin-bottom: 15px; padding-left: 20px; }}
            li {{ margin-bottom: 5px; }}
            blockquote {{ 
                margin: 15px 0; 
                padding: 10px 15px; 
                border-left: 4px solid #ccc; 
                background-color: #f9f9f9; 
                color: #555;
            }}
            p {{ margin-bottom: 15px; }}
        </style>
        </head>
        <body>
            {raw_html}
        </body>
        </html>
        """
    except ImportError:
        # Fallback manual ganti newline ke <br> dan hapus markdown symbol dasar
        html_body = body.replace("\n", "<br>").replace("**", "<b>").replace("* ", "<li>")
        
    # Gunakan multipart/alternative agar mendukung email client jadul dan modern
    msg_alt = MIMEMultipart('alternative')
    msg.attach(msg_alt)
    
    msg_alt.attach(MIMEText(body, 'plain'))
    msg_alt.attach(MIMEText(html_body, 'html'))
    
    # Sisipkan file lampiran jika ada
    if attachments:
        from email.mime.base import MIMEBase
        from email import encoders
        import base64
        for att in attachments:
            fname = att.get("filename", "attachment")
            fbytes = att.get("content_bytes")
            if not fbytes and att.get("content_base64"):
                b64_str = att["content_base64"]
                if "," in b64_str:
                    b64_str = b64_str.split(",", 1)[1]
                try:
                    fbytes = base64.b64decode(b64_str)
                except Exception as e_b64:
                    logger.warning(f"[ZIMBRA] Failed to decode base64 attachment {fname}: {e_b64}")
                    continue
            if fbytes:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(fbytes)
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{fname}"')
                msg.attach(part)
    
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
