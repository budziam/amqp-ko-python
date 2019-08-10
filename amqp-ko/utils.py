import enum
from datetime import date, datetime

import aio_pika


def serializer(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    if isinstance(obj, enum.Enum):
        return obj.value

    raise TypeError(f"Type {type(obj)} not serializable")


def get_header_value(message: aio_pika.Message, key: str, default: any = None) -> any:
    headers = message.headers or {}
    return headers.get(key, default)
