class InvalidRoutingKeyException(Exception):
    def __init__(self, routing_key: str) -> None:
        super().__init__(f"Invalid message routing key: [{routing_key}]")


class InvalidMessageTypeException(Exception):
    def __init__(self, message_type: type) -> None:
        super().__init__(f"Invalid message type: [{message_type}]")
