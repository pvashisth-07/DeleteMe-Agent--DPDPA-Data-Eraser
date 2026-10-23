from typing import Any, Callable, Coroutine, List, Optional
from uuid import uuid4

from uagents import Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    MetadataContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

from shared.clock import now


def make_text_reply(
    text: str,
    end_session: bool = False,
    metadata: Optional[dict] = None,
) -> ChatMessage:
    content: List[Any] = [TextContent(type="text", text=text)]
    if metadata:
        content.append(MetadataContent(type="metadata", metadata=metadata))
    if end_session:
        content.append(EndSessionContent())

    return ChatMessage(
        timestamp=int(now().timestamp()),
        msg_id=uuid4(),
        content=content,
    )


async def send_ack(ctx: Context, sender: str, msg: ChatMessage) -> None:
    ack = ChatAcknowledgement(
        timestamp=int(now().timestamp()),
        acknowledged_msg_id=msg.msg_id,
        metadata={},
    )
    await ctx.send(sender, ack)


def build_chat_protocol(
    handler: Callable[[Context, str, ChatMessage], Coroutine[Any, Any, None]],
    on_ack: Optional[Callable[[Context, str, ChatAcknowledgement], Coroutine[Any, Any, None]]] = None,
) -> Protocol:
    """Builds a standardized ACP Protocol implementing both ChatMessage and ChatAcknowledgement interactions."""
    proto = Protocol(spec=chat_protocol_spec)

    @proto.on_message(model=ChatMessage)
    async def _on_chat_message(ctx: Context, sender: str, msg: ChatMessage):
        # Invariant 1: Always acknowledge first
        await send_ack(ctx, sender, msg)
        # Invariant 2: Delegate to custom handler
        await handler(ctx, sender, msg)

    @proto.on_message(model=ChatAcknowledgement)
    async def _on_chat_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
        if on_ack:
            await on_ack(ctx, sender, msg)

    return proto
