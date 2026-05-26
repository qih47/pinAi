from pydantic import BaseModel


class OCRContent(BaseModel):
    content: str
