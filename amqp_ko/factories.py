from typing import List

import aio_pika

from amqp_ko.models import MessageGate
from amqp_ko.queue import Queue, MessageGateCollection


async def create_queue(
    connection: aio_pika.Connection,
    exchange: str,
    message_gates: List[MessageGate],
    prefetch_count: int = 5,
) -> Queue:
    message_gate_collection = MessageGateCollection(message_gates)

    consume_channel = await connection.channel(1, publisher_confirms=False)
    await consume_channel.set_qos(prefetch_count=prefetch_count)
    produce_channel = await connection.channel(2, publisher_confirms=False)
    delay_channel = await connection.channel(3, publisher_confirms=False)

    return Queue(
        consume_channel,
        produce_channel,
        delay_channel,
        message_gate_collection,
        exchange,
    )
