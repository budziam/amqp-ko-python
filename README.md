# AMQP Kø 
Object oriented AMQP layer for microservices communication.

## Usage
The recommended way to use AMQP Kø is to create your own queue object. The simplest way to do this is using `createQueue` function.

### Create queue
```python
from amqp_ko import create_queue, AsyncConnection, Message, MessageGate
from dataclasses import dataclass


@dataclass(frozen=True)
class TopicFollow(Message):
    user_id: int
    topic_name: str


def unmarshal_topic_follow(data: dict) -> TopicFollow:
    return TopicFollow(
        user_id=data["user_id"],
        topic_name=data["topic_name"],
    )

message_gates = [
    MessageGate("topic_follow", TopicFollow, unmarshal_topic_follow),
]

async with AsyncConnection("localhost", 5672, "rabbitmq", "rabbitmq") as connection:
    queue = await create_queue(connection, "exchange-name", message_gates)
```

### Consume messages
```python
from amqp_ko import Consumer, Job


class ConnectUserWithTopic(Consumer):
    async def consume(self, job: Job):
        # Put here some code to connect user with a topic
        # using "job.message.userId" and "job.message.topicName"
        await job.ack()
        
await queue.consume(
    "queue-name",
    {TopicFollow: ConnectUserWithTopic()},
)
```

### Produce message
```python
message = TopicFollow(120, "entertainment")
await queue.produce(message)
```

## Installation
```bash
pip install amqp-ko
```

#### Author: [Michał Budziak]

[Michał Budziak]: http://github.com/budziam
