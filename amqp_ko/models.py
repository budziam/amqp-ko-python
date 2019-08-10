import asyncio
import json
import logging
from abc import abstractmethod
from dataclasses import dataclass
from typing import List, Generic, TypeVar, Callable

import aio_pika
from aio_pika import MessageProcessError
from cached_property import cached_property

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class Message:
    pass


@dataclass
class MessageGate:
    routing_key: str
    message_type: type
    unmarshaller: Callable[[dict], Message]


class Job(Generic[T]):
    """
    Adapter for aio_pika.IncomingMessage
    """

    def __init__(self, queue, incoming_message: aio_pika.IncomingMessage, message: T):
        self.__queue = queue
        self.__incoming_message = incoming_message
        self.__message = message

    @cached_property
    def body(self):
        return json.loads(self.__incoming_message.body)

    @property
    def message(self) -> T:
        return self.__message

    def ack(self):
        try:
            self.__incoming_message.ack()
        except MessageProcessError:
            pass

    def nack(self):
        try:
            self.__incoming_message.nack()
        except MessageProcessError:
            pass

    async def requeue(self):
        if self.__incoming_message.processed:
            return

        await self.__queue.requeue(self.__incoming_message)


class Consumer:
    @abstractmethod
    async def consume(self, job: Job) -> None:
        raise NotImplementedError()


class BatchConsumer:
    @abstractmethod
    async def consume(self, jobs: List[Job]) -> None:
        raise NotImplementedError()


class AccumulativeConsumer(Consumer):
    DEFAULT_BATCH_SIZE = 500
    DEFAULT_TIMEOUT = 0.2  # in seconds

    def __init__(
        self,
        consumer: BatchConsumer,
        batch_size=DEFAULT_BATCH_SIZE,
        timeout=DEFAULT_TIMEOUT,
    ):
        self._loop = asyncio.get_event_loop()
        self._consumer = consumer
        self._batch_size = batch_size
        self._timeout = timeout
        self._jobs = []
        self._timeout_task = None

    async def _consume_jobs(self, jobs: List[Job]) -> None:
        if not jobs:
            return

        try:
            await self._consumer.consume(jobs)

            for job in jobs:
                job.ack()
        except Exception:
            logger.exception(
                "Could not consume jobs batch", extra={"batch_size": len(jobs)}
            )

            for job in jobs:
                await job.requeue()

    async def consume(self, job: Job) -> None:
        if self._timeout_task:
            self._timeout_task.cancel()

        self._jobs.append(job)

        jobs = self._jobs
        if len(jobs) >= self._batch_size:
            self._jobs = []
            await self._consume_jobs(jobs)
            return

        self._timeout_task = self._loop.create_task(asyncio.sleep(self._timeout))
        try:
            await self._timeout_task
            self._jobs = []
            await self._consume_jobs(jobs)
        except asyncio.CancelledError:
            pass


class SingleConsumer(Consumer):
    def __init__(self, consumer: Consumer):
        self._consumer = consumer

    async def consume(self, job: Job) -> None:
        await self._consumer.consume(job)
        job.ack()
