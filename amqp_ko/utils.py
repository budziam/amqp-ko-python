import enum
from datetime import date, datetime


def serializer(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    if isinstance(obj, enum.Enum):
        return obj.value

    raise TypeError(f"Type {type(obj)} not serializable")
