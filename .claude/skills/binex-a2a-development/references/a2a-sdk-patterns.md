# A2A SDK Patterns for Binex

## Table of Contents
1. [Agent Server (JSON-RPC)](#agent-server-json-rpc)
2. [Agent Server (REST)](#agent-server-rest)
3. [AgentExecutor Protocol](#agentexecutor-protocol)
4. [Agent Card Definition](#agent-card-definition)
5. [Streaming & Artifact Chunks](#streaming--artifact-chunks)
6. [A2A Client (Sending Tasks)](#a2a-client-sending-tasks)
7. [Task State Machine](#task-state-machine)

## Agent Server (JSON-RPC)

Standard A2A server with JSON-RPC transport:

```python
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.apps import A2AFastAPIApplication
from a2a.types import (
    AgentCard, AgentCapabilities, AgentSkill,
    Task, TaskStatus, TaskState, TaskStatusUpdateEvent
)
from a2a.utils.message import new_agent_text_message

class MyAgent(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue):
        user_text = context.message.parts[0].root.text if context.message else ""

        # Signal working
        await event_queue.put(TaskStatusUpdateEvent(
            task_id=context.task_id,
            context_id=context.context_id,
            status=TaskStatus(state=TaskState.working),
            final=False
        ))

        # Complete with result
        await event_queue.put(Task(
            id=context.task_id,
            context_id=context.context_id,
            status=TaskStatus(
                state=TaskState.completed,
                message=new_agent_text_message(
                    f"Result: {user_text}",
                    context.context_id,
                    context.task_id
                )
            )
        ))

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        await event_queue.put(Task(
            id=context.task_id,
            context_id=context.context_id,
            status=TaskStatus(state=TaskState.canceled)
        ))

agent_card = AgentCard(
    name="My Agent",
    description="Does something useful",
    url="http://localhost:8000",
    version="1.0.0",
    capabilities=AgentCapabilities(streaming=True),
    skills=[
        AgentSkill(id="skill-1", name="Skill", description="...", tags=["tag"])
    ],
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"]
)

handler = DefaultRequestHandler(MyAgent(), InMemoryTaskStore())
app = A2AFastAPIApplication(agent_card, handler).build()
# Endpoints: POST /rpc, GET /.well-known/agent-card.json
```

## Agent Server (REST)

REST transport (non-JSON-RPC):

```python
from a2a.server.apps import A2ARESTFastAPIApplication

app = A2ARESTFastAPIApplication(agent_card, handler).build()
# Endpoints:
#   POST /message/send
#   POST /message/stream
#   POST /tasks/get
#   POST /tasks/cancel
#   GET /.well-known/agent-card.json
```

## AgentExecutor Protocol

Every agent implements `AgentExecutor`:

```python
class AgentExecutor(Protocol):
    async def execute(self, context: RequestContext, event_queue: EventQueue): ...
    async def cancel(self, context: RequestContext, event_queue: EventQueue): ...
```

`RequestContext` fields:
- `context.task_id` — current task ID
- `context.context_id` — conversation/context ID
- `context.message` — incoming message with `.parts[]`

`EventQueue` accepts:
- `TaskStatusUpdateEvent` — intermediate status updates
- `Task` — final task result (completed/failed/canceled)
- `TaskArtifactUpdateEvent` — streaming artifact chunks

## Agent Card Definition

```python
AgentCard(
    name="Agent Name",
    description="What this agent does",
    url="http://host:port",
    version="1.0.0",
    capabilities=AgentCapabilities(
        streaming=True,
        supports_push_notification=False
    ),
    skills=[
        AgentSkill(
            id="unique-id",
            name="Human Name",
            description="Capability description",
            tags=["keyword1", "keyword2"]
        )
    ],
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"]
)
```

## Streaming & Artifact Chunks

Stream large outputs in chunks:

```python
from a2a.types import TaskArtifactUpdateEvent, Artifact, Part, TextPart
from uuid import uuid4

artifact_id = str(uuid4())
for i, chunk in enumerate(chunks):
    await event_queue.put(TaskArtifactUpdateEvent(
        task_id=context.task_id,
        context_id=context.context_id,
        artifact=Artifact(
            artifact_id=artifact_id,
            name="output.txt",
            parts=[Part(root=TextPart(text=chunk))]
        ),
        append=True,
        last_chunk=(i == len(chunks) - 1)
    ))
```

## A2A Client (Sending Tasks)

```python
from a2a.client import A2AClient
import httpx

client = A2AClient(httpx_client=httpx.AsyncClient(), url="http://agent:8000")

# Discover agent
card = await client.get_agent_card()

# Send message
from a2a.types import MessageSendParams, Message, Part, TextPart
response = await client.send_message(MessageSendParams(
    message=Message(
        role="user",
        parts=[Part(root=TextPart(text="Do something"))],
        message_id="msg-1"
    )
))
```

## Task State Machine

```
submitted -> working -> completed
                     -> failed
                     -> canceled
                     -> input-required
```

Map to Binex TaskStatus:
- `submitted` / `working` -> `running`
- `completed` -> `completed`
- `failed` -> `failed`
- `canceled` -> `cancelled`
- `input-required` -> not supported in Binex MVP
