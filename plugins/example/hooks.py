"""Example plugin event hooks."""
from app import event_bus


@event_bus.subscribe("memory.added")
async def on_memory_added(event):
    """Called when a new memory is added."""
    data = event.get("data", {})
    content = data.get("content", "")[:50]
    print(f"[example plugin] saw new memory: {content}")


@event_bus.subscribe("conversation.ended")
async def on_conversation_ended(event):
    """Called when a conversation ends."""
    print(f"[example plugin] conversation ended: {event.get('data', {})}")
