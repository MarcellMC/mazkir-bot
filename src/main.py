"""Main entry point for Mazkir bot."""
import asyncio
import logging
from telethon import TelegramClient, events
from src.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.debug else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main bot entry point"""

    # Validate configuration
    try:
        settings.validate_config()
    except AssertionError as e:
        logger.error(f"Configuration error: {e}")
        print(f"❌ Configuration error: {e}")
        print("Please check your .env file and ensure all required variables are set.")
        return
    except Exception as e:
        logger.error(f"Unexpected error during config validation: {e}", exc_info=True)
        return

    logger.info("Starting Mazkir bot...")

    # Import handlers here (after config validation)
    try:
        from src.bot.handlers import get_handlers
    except Exception as e:
        logger.error(f"Error importing handlers: {e}", exc_info=True)
        return

    # Create Telegram client (bot mode)
    client = TelegramClient(
        'mazkir_bot_session',
        settings.telegram_api_id,
        settings.telegram_api_hash
    )

    # Register handlers
    handlers = get_handlers()
    for handler_func, event_builder in handlers:
        client.add_event_handler(handler_func, event_builder)

    logger.info("Handlers registered")

    # Start client in bot mode
    await client.start(bot_token=settings.telegram_bot_token)

    # Get bot info to verify which bot is running
    me = await client.get_me()
    print(f"\n{'='*60}")
    print(f"✅ Mazkir Bot is running!")
    print(f"{'='*60}")
    print(f"Bot username: @{me.username}")
    print(f"Bot name: {me.first_name}")
    print(f"Bot ID: {me.id}")
    print(f"{'='*60}")
    print(f"Vault: {settings.vault_path}")
    print(f"Authorized user ID: {settings.authorized_user_id}")
    print(f"{'='*60}")
    print(f"\n👉 Message @{me.username} on Telegram to interact")
    print("Press Ctrl+C to stop\n")

    logger.info("Bot started successfully!")
    logger.info(f"Bot: @{me.username}")
    logger.info(f"Vault: {settings.vault_path}")
    logger.info(f"Authorized user: {settings.authorized_user_id}")

    # Run until disconnected
    await client.run_until_disconnected()


if __name__ == '__main__':
    asyncio.run(main())
