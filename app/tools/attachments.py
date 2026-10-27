from app.models.schemas import AttachmentReport


async def check_attachments(raw_payload: dict) -> AttachmentReport:
    attachments = raw_payload.get("attachments", [])
    if not isinstance(attachments, list):
        raise ValueError("attachments must be a list")
    names = [
        str(item.get("file_name") or item.get("filename") or "unnamed")
        for item in attachments
        if isinstance(item, dict)
    ]
    return AttachmentReport(present=names, count=len(names))
