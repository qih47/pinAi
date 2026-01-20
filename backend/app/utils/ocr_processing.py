import logging
import base64


async def process_pdf_attachment_to_ocr(
    attachment, npp, session_id, get_embedding_func
):
    """
    Hanya bertugas sebagai gateway/wrapper untuk memanggil
    OCR processor utama tanpa redundansi library.
    """
    try:
        from ..services.ocr.ocr_processor import (
            process_pdf_attachment_to_ocr as ocr_logic,
        )

        base64_data = attachment.get("data", "")
        if not base64_data:
            logging.warning("⚠️ Attachment tidak memiliki data base64.")
            return ""
        if "," in base64_data:
            attachment["data"] = base64_data.split(",")[1]
        extracted_text = await ocr_logic(
            attachment=attachment,
            npp=npp,
            session_id=session_id,
            get_embedding_func=get_embedding_func,
        )

        return extracted_text

    except ImportError as ie:
        logging.error(
            f"❌ Kesalahan Path Import: {ie}. Pastikan folder 'app/services/ocr' benar."
        )
        return ""
    except Exception as e:
        logging.error(f"❌ Error in OCR wrapper: {e}")
        return ""
