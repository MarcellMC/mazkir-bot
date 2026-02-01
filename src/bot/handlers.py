"""Message and command handlers for the bot."""
import logging

from telethon import events

from src.bot.client import MazkirClient
from src.services.message_ingestion import MessageIngestionService
from src.services.llm_service import LLMService
from src.services.embedding_service import EmbeddingService
from src.database.connection import async_session_maker
from src.database.repository import MessageRepository

logger = logging.getLogger(__name__)


class BotHandlers:
    """Handle bot commands and messages."""

    def __init__(self, client: MazkirClient):
        self.client = client
        self.ingestion_service = MessageIngestionService(client)
        self.llm_service = LLMService(provider="ollama")
        self.embedding_service = EmbeddingService()

    def register(self):
        """Register all handlers."""
        self.client.client.add_event_handler(
            self.handle_start, events.NewMessage(pattern="/start")
        )
        self.client.client.add_event_handler(
            self.handle_help, events.NewMessage(pattern="/help")
        )
        self.client.client.add_event_handler(
            self.handle_sync, events.NewMessage(pattern=r"/sync(\s+\d+)?")
        )
        self.client.client.add_event_handler(
            self.handle_analyze, events.NewMessage(pattern=r"/analyze(\s+\d+)?")
        )
        self.client.client.add_event_handler(
            self.handle_search, events.NewMessage(pattern=r"/search\s+.+")
        )

    async def handle_start(self, event):
        """Handle /start command."""
        await event.respond(
            "Welcome to Mazkir!\n\n"
            "I can help you analyze your Telegram messages and provide insights.\n\n"
            "Use /help to see available commands."
        )

    async def handle_help(self, event):
        """Handle /help command."""
        help_text = """
Available commands:

/start - Start the bot
/help - Show this help message
/sync [limit] - Fetch and store messages from Saved Messages (default: 100)
/analyze [limit] - Analyze recent stored messages (default: 50)
/search <query> - Search messages by semantic meaning

Example:
/sync 200 - Fetch 200 messages
/analyze 100 - Analyze 100 recent messages
/search programming tutorials - Find messages about programming
        """
        await event.respond(help_text.strip())

    async def handle_sync(self, event):
        """Handle /sync command to fetch and store messages."""
        # Parse limit from command
        text = event.raw_text.strip()
        parts = text.split()
        limit = 100  # default

        if len(parts) > 1:
            try:
                limit = int(parts[1])
                limit = min(limit, 1000)  # Cap at 1000
            except ValueError:
                await event.respond("Invalid limit. Usage: /sync [number]")
                return

        await event.respond(f"Fetching up to {limit} messages from Saved Messages...")

        try:
            stats = await self.ingestion_service.ingest_saved_messages(limit=limit)

            response = f"""
Sync complete!

Fetched: {stats['total_fetched']} messages
Newly stored: {stats['new_stored']}
Already existed: {stats['already_exists']}
Skipped (no text): {stats['skipped_no_text']}
Errors: {stats['errors']}
            """
            await event.respond(response.strip())

        except Exception as e:
            logger.error(f"Error during sync: {e}", exc_info=True)
            await event.respond(f"Error during sync: {str(e)}")

    async def handle_analyze(self, event):
        """Handle /analyze command to analyze stored messages."""
        # Parse limit from command
        text = event.raw_text.strip()
        parts = text.split()
        limit = 50  # default

        if len(parts) > 1:
            try:
                limit = int(parts[1])
                limit = min(limit, 200)  # Cap at 200
            except ValueError:
                await event.respond("Invalid limit. Usage: /analyze [number]")
                return

        await event.respond(f"Analyzing {limit} recent messages...")

        try:
            # Get recent messages from database
            async with async_session_maker() as session:
                repo = MessageRepository(session)
                # Use sender_id "me" to get user's own chat
                messages = await repo.get_recent_messages(chat_id=event.chat_id, limit=limit)

            if not messages:
                await event.respond("No messages found. Use /sync first to fetch messages.")
                return

            # Extract text from messages
            message_texts = [msg.text for msg in messages if msg.text]

            if not message_texts:
                await event.respond("No text messages found to analyze.")
                return

            # Analyze with LLM
            analysis = await self.llm_service.analyze_messages(message_texts)

            # Send response
            await event.respond(f"Analysis of {len(message_texts)} messages:\n\n{analysis}")

        except Exception as e:
            logger.error(f"Error during analysis: {e}", exc_info=True)
            await event.respond(f"Error during analysis: {str(e)}")

    async def handle_search(self, event):
        """Handle /search command for semantic search."""
        # Extract query from command
        text = event.raw_text.strip()

        # Remove '/search ' prefix
        if not text.startswith('/search '):
            await event.respond("Usage: /search <your query>\n\nExample: /search programming tutorials")
            return

        query = text[8:].strip()  # Remove '/search '

        if not query:
            await event.respond("Please provide a search query.\n\nExample: /search machine learning")
            return

        await event.respond(f"Searching for: {query}...")

        try:
            # Generate embedding for the query
            query_embedding = await self.embedding_service.embed_text(query)

            # Search for similar messages
            async with async_session_maker() as session:
                repo = MessageRepository(session)
                similar_messages = await repo.search_similar(
                    embedding=query_embedding,
                    limit=10
                )

            if not similar_messages:
                await event.respond("No messages found. Try syncing messages first with /sync")
                return

            # Format results
            response = f"Found {len(similar_messages)} similar messages:\n\n"

            for i, msg in enumerate(similar_messages, 1):
                # Format date
                date_str = msg.date.strftime("%Y-%m-%d")

                # Truncate long messages
                text_preview = msg.text[:150] if msg.text else "[No text]"
                if len(msg.text or "") > 150:
                    text_preview += "..."

                response += f"{i}. [{date_str}] {text_preview}\n\n"

            # Split response if too long (Telegram limit is ~4096 chars)
            if len(response) > 4000:
                # Send in chunks
                chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
                for chunk in chunks:
                    await event.respond(chunk)
            else:
                await event.respond(response.strip())

        except Exception as e:
            logger.error(f"Error during search: {e}", exc_info=True)
            await event.respond(f"Error during search: {str(e)}")
