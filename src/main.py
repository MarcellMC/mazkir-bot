"""Main entry point for Mazkir bot."""
import asyncio
import logging

from src.bot.client import MazkirClient
from src.bot.handlers import BotHandlers
from src.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def main():
    """Run the bot."""
    logger.info("Starting Mazkir bot...")

    # Initialize client
    client = MazkirClient()

    try:
        # Start client
        await client.start()

        # Register handlers
        handlers = BotHandlers(client)
        handlers.register()

        logger.info("Bot is running. Press Ctrl+C to stop.")

        # Keep the bot running
        await client.client.run_until_disconnected()

    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Error running bot: {e}", exc_info=True)
    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
