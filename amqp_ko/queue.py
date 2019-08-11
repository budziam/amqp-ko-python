import asyncio
import json
import logging
from dataclasses import asdict
from random import randint
from typing import Dict, List

import aio_pika

from amqp_ko.exceptions import InvalidRoutingKeyException, InvalidMessageTypeException
from amqp_ko.models import Consumer, Job, MessageGate, Message
from amqp_ko.utils import serializer, get_header_value

logger = logging.getLogger(__name__)


X_DELAY = "x-delay"
X_ATTEMPTS = "x-attempts"
MAX_DELAY = 30 * 60


def calculate_requeue_backoff(message: aio_pika.Message) -> int:
    attempts = get_header_value(message, X_ATTEMPTS, 1)
    delay = randint(1, 2 ** (3 + attempts))
    return min(MAX_DELAY, delay) * 1000


def handle_invalid_message(message: aio_pika.IncomingMessage) -> None:
    logger.info(
        "Received invalid message",
        extra={"msg_routing_key": message.routing_key, "msg_body": message.body},
    )

    message.ack()


class MessageGateCollection:
    def __init__(self, message_gates: List[MessageGate]):
        self._message_gates = message_gates

    def get_by_routing_key(self, routing_key: str) -> MessageGate:
        for message_gate in self._message_gates:
            if message_gate.routing_key == routing_key:
                return message_gate

        raise InvalidRoutingKeyException(routing_key)

    def get_by_message_type(self, message_type: type) -> MessageGate:
        for message_gate in self._message_gates:
            if message_gate.message_type == message_type:
                return message_gate

        raise InvalidMessageTypeException(message_type)


class AsyncConnection:
    def __init__(self, host: str, port: int, username: str, password: str):
        self._event_loop = asyncio.get_event_loop()
        self._password = password
        self._username = username
        self._port = port
        self._host = host
        self._connection = None

    async def __aenter__(self):
        self._connection = await aio_pika.connect_robust(
            host=self._host,
            port=self._port,
            login=self._username,
            password=self._password,
            loop=self._event_loop,
        )
        return self._connection

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._connection.close()


class Queue:
    def __init__(
        self,
        consume_channel: aio_pika.Channel,
        produce_channel: aio_pika.Channel,
        delay_channel: aio_pika.Channel,
        message_gates: MessageGateCollection,
        exchange: str,
    ) -> None:
        self._consume_channel = consume_channel
        self._produce_channel = produce_channel
        self._delay_channel = delay_channel
        self._exchange_name = exchange
        self._message_gates = message_gates

    async def consume(self, queue_name: str, consumers: Dict[type, Consumer]):
        await self._declare_exchange(self._consume_channel)
        queue: aio_pika.Queue = await self._consume_channel.declare_queue(
            name=queue_name, durable=True
        )

        for message_type in consumers.keys():
            gate = self._message_gates.get_by_message_type(message_type)
            await queue.bind(self._exchange_name, gate.routing_key)

        async with queue.iterator() as iterator:
            async for message in iterator:
                asyncio.ensure_future(self._process_message(message, consumers))

    async def produce(self, message: Message) -> None:
        gate = self._message_gates.get_by_message_type(type(message))

        exchange = await self._declare_exchange(self._produce_channel)
        queue_message = aio_pika.Message(
            body=json.dumps(asdict(message), default=serializer).encode("utf-8"),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await exchange.publish(queue_message, gate.routing_key)

    async def requeue(self, message: aio_pika.IncomingMessage) -> None:
        await self.requeue_later(message, calculate_requeue_backoff(message))

    async def requeue_later(
        self, message: aio_pika.IncomingMessage, delay: int
    ) -> None:
        exchange = await self._declare_exchange(self._delay_channel)
        delay_exchange = await self._delay_channel.declare_exchange(
            name=f"{self._exchange_name}_delayed",
            type=aio_pika.ExchangeType.X_DELAYED_MESSAGE,
            durable=True,
            arguments={"x-delayed-type": aio_pika.ExchangeType.FANOUT.value},
        )

        await exchange.bind(delay_exchange)

        queue_message = aio_pika.Message(
            body=message.body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            headers={
                X_DELAY: delay,
                X_ATTEMPTS: get_header_value(message, X_ATTEMPTS, 1) + 1,
            },
        )

        # Publish message with a given delay. Next reject old message
        # otherwise we would end up with loosing a message.
        await delay_exchange.publish(queue_message, message.routing_key)
        message.reject()

        logger.info(
            "Message was requeued",
            extra={
                "msg_routing_key": message.routing_key,
                "msg_body": message.body,
                "msg_attempts": get_header_value(queue_message, X_ATTEMPTS),
                "msg_delay": get_header_value(queue_message, X_DELAY),
            },
        )

    async def _process_message(
        self,
        incoming_message: aio_pika.IncomingMessage,
        consumers: Dict[type, Consumer],
    ) -> None:
        try:
            gate = self._message_gates.get_by_routing_key(incoming_message.routing_key)
            consumer = consumers.get(gate.message_type)
            body = json.loads(incoming_message.body)
            message = gate.unmarshaller(body)
            job = Job(self, incoming_message, message)
        except (InvalidMessageTypeException, InvalidRoutingKeyException):
            return handle_invalid_message(incoming_message)
        except Exception:
            logger.exception(
                "Could not unserialize message",
                extra={
                    "msg_routing_key": incoming_message.routing_key,
                    "msg_body": incoming_message.body,
                    "msg_attempts": get_header_value(incoming_message, X_ATTEMPTS, 1),
                },
            )
            await self.requeue(incoming_message)
            return

        try:
            await consumer.consume(job)
        except Exception:
            # Job could be requeued in a consume method, so we need to
            # use job requeue method to ensure we would not requeue it twice
            logger.exception(
                "Could not consume message",
                extra={
                    "msg_routing_key": incoming_message.routing_key,
                    "msg_body": incoming_message.body,
                    "msg_attempts": get_header_value(incoming_message, X_ATTEMPTS, 1),
                },
            )
            await job.requeue()

    async def _declare_exchange(self, channel: aio_pika.Channel) -> aio_pika.Exchange:
        return await channel.declare_exchange(
            name=self._exchange_name, type=aio_pika.ExchangeType.TOPIC, durable=True
        )
