"""Message factory functions."""

from ..core.types import Message, MessageType


def create_goal_message(
    sender: str,
    recipient: str,
    goal_description: str,
    goal_id: str | None = None,
    correlation_id: str | None = None,
) -> Message:
    """Create a goal delegation message."""
    return Message(
        type=MessageType.GOAL,
        sender=sender,
        recipient=recipient,
        content=goal_description,
        goal_id=goal_id,
        correlation_id=correlation_id,
    )


def create_result_message(
    sender: str,
    recipient: str,
    result: str,
    goal_id: str | None = None,
    correlation_id: str | None = None,
) -> Message:
    """Create a result reply message."""
    return Message(
        type=MessageType.RESULT,
        sender=sender,
        recipient=recipient,
        content=result,
        goal_id=goal_id,
        correlation_id=correlation_id,
    )


def create_reply(
    original: Message,
    sender: str,
    content: str,
    message_type: MessageType = MessageType.RESPONSE,
) -> Message:
    """Create a reply to an existing message, preserving correlation."""
    return Message(
        type=message_type,
        sender=sender,
        recipient=original.sender,
        content=content,
        correlation_id=original.correlation_id or original.message_id,
        in_reply_to=original.message_id,
        goal_id=original.goal_id,
    )
