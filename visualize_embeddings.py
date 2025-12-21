"""Visualize message embeddings in 2D space using dimensionality reduction."""
import asyncio
import numpy as np
from datetime import datetime
from sqlalchemy import select

from src.database.connection import async_session_maker
from src.database.models import Message


async def fetch_messages_with_embeddings():
    """Fetch all messages with embeddings from database."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Message)
            .where(Message.embedding.isnot(None))
            .order_by(Message.date)
        )
        messages = list(result.scalars().all())

    print(f"Fetched {len(messages)} messages with embeddings")
    return messages


async def main():
    """Main function to create visualization."""
    print("=" * 60)
    print("Vector Space Visualization")
    print("=" * 60)

    # Fetch messages
    print("\n1. Fetching messages from database...")
    messages = await fetch_messages_with_embeddings()

    if len(messages) < 2:
        print("Error: Need at least 2 messages to create visualization")
        return

    # Extract embeddings and metadata
    print("\n2. Extracting embeddings and metadata...")
    embeddings = np.array([msg.embedding for msg in messages])
    texts = [msg.text[:100] if msg.text else "" for msg in messages]  # Truncate for display
    dates = [msg.date for msg in messages]

    print(f"   - Embeddings shape: {embeddings.shape}")
    print(f"   - Date range: {min(dates)} to {max(dates)}")

    # Save data for visualization script
    np.savez(
        'embeddings_data.npz',
        embeddings=embeddings,
        texts=np.array(texts),
        dates=np.array([d.isoformat() for d in dates])
    )

    print("\n✓ Data prepared and saved to 'embeddings_data.npz'")
    print("\nNext: Run the visualization script to create the plot")


if __name__ == "__main__":
    asyncio.run(main())
