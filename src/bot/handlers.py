"""Message and command handlers for the bot."""
from telethon import events, Button
from datetime import datetime
import pytz
from dateutil import parser as dateutil_parser
from src.config import settings
from src.services.vault_service import VaultService
from src.services.claude_service import ClaudeService

# Initialize services
vault = VaultService(settings.vault_path, settings.vault_timezone)
claude = ClaudeService(
    api_key=settings.anthropic_api_key,
    vault_path=str(settings.vault_path),
    timezone=settings.vault_timezone
)
tz = pytz.timezone(settings.vault_timezone)


# Middleware: Only allow authorized user
def authorized_only(func):
    """Decorator to restrict commands to authorized user"""
    async def wrapper(event):
        if event.sender_id != settings.authorized_user_id:
            await event.respond("⛔ Unauthorized. This bot is for Marc's personal use only.")
            return
        return await func(event)
    return wrapper


@authorized_only
async def cmd_start(event):
    """Welcome message"""
    await event.respond(
        "👋 **Welcome to Mazkir!**\n\n"
        "Your Personal AI Assistant for productivity and motivation.\n\n"
        "**Quick commands:**\n"
        "/day - Today's note\n"
        "/tasks - Active tasks\n"
        "/habits - Habit tracker\n"
        "/tokens - Token balance\n"
        "/help - Full command list\n\n"
        "**Or just chat naturally:**\n"
        "• \"I completed gym\"\n"
        "• \"Show my streaks\"\n"
        "• \"Create task: buy milk\""
    )
    raise events.StopPropagation


@authorized_only
async def cmd_day(event):
    """Show today's daily note"""
    try:
        # Read today's daily note
        daily = vault.read_daily_note()
        metadata = daily['metadata']

        # Format response
        date = datetime.now(tz)
        day_name = metadata.get('day_of_week', date.strftime('%A'))

        response = f"📅 **{day_name}, {date.strftime('%B %d, %Y')}**\n\n"

        # Tokens
        tokens_today = metadata.get('tokens_earned', 0)
        tokens_total = metadata.get('tokens_total', 0)
        response += f"🪙 **Tokens Today:** {tokens_today}\n"
        response += f"💰 **Total Bank:** {tokens_total} tokens\n\n"

        # Habits
        response += "🎯 **Daily Habits**\n"
        completed_habits = metadata.get('completed_habits', [])

        # Get all active habits to show status
        active_habits = vault.list_active_habits()
        for habit_data in active_habits:
            habit_meta = habit_data['metadata']
            habit_name = habit_meta.get('name', 'Unknown')

            if habit_name in completed_habits:
                streak = habit_meta.get('streak', 0)
                response += f"✅ {habit_name} ({streak} day streak)\n"
            else:
                response += f"⏳ {habit_name}\n"

        response += "\n"

        # Tasks (from daily note content)
        # This is simplified - you might want to parse the markdown content
        response += "📋 **Tasks**\n"
        response += "_See /tasks for full list_\n\n"

        # Buttons
        buttons = [
            [Button.inline("✏️ Edit Note", b"edit_note")],
            [Button.inline("📊 Full Details", b"full_note")]
        ]

        await event.respond(response, buttons=buttons)

    except FileNotFoundError:
        await event.respond(
            "📝 No daily note for today yet.\n\n"
            "Would you like me to create one?",
            buttons=[
                [Button.inline("✅ Create Note", b"create_note")],
                [Button.inline("❌ Cancel", b"cancel")]
            ]
        )
    except Exception as e:
        await event.respond(f"❌ Error reading daily note: {str(e)}")

    raise events.StopPropagation


@authorized_only
async def cmd_tasks(event):
    """Show active tasks"""
    try:
        tasks = vault.list_active_tasks()

        if not tasks:
            await event.respond("✅ No active tasks! You're all caught up.")
            raise events.StopPropagation

        response = "📋 **Active Tasks**\n\n"

        # Group by priority
        high_priority = [t for t in tasks if t['metadata'].get('priority', 3) >= 4]
        medium_priority = [t for t in tasks if t['metadata'].get('priority', 3) == 3]
        low_priority = [t for t in tasks if t['metadata'].get('priority', 3) <= 2]

        today = datetime.now(tz).date()

        def format_task(task):
            """Extract task name from markdown heading"""
            meta = task['metadata']
            content = task['content']

            # Try to get name from metadata first
            name = meta.get('name')

            # If no name in metadata, extract from first markdown heading
            if not name:
                for line in content.split('\n'):
                    line = line.strip()
                    if line.startswith('#'):
                        # Remove markdown heading markers
                        name = line.lstrip('#').strip()
                        break

            if not name:
                name = 'Unnamed task'

            return name

        if high_priority:
            response += "🔴 **High Priority**\n"
            for task in high_priority:
                meta = task['metadata']
                name = format_task(task)
                due_date = meta.get('due_date')

                status = ""
                if due_date:
                    # Convert to date if it's not already
                    if isinstance(due_date, str):
                        due_date = dateutil_parser.parse(due_date).date()

                    if due_date < today:
                        status = f" (overdue: {due_date})"
                    elif due_date == today:
                        status = " (due today)"

                response += f"• {name}{status}\n"
            response += "\n"

        if medium_priority:
            response += "🟡 **Medium Priority**\n"
            for task in medium_priority:
                name = format_task(task)
                response += f"• {name}\n"
            response += "\n"

        if low_priority:
            response += "🟢 **Low Priority**\n"
            for task in low_priority:
                name = format_task(task)
                response += f"• {name}\n"
            response += "\n"

        response += f"---\nTotal: {len(tasks)} active tasks"

        buttons = [
            [Button.inline("➕ Add Task", b"add_task")],
            [Button.inline("✅ Complete Task", b"complete_task")]
        ]

        await event.respond(response, buttons=buttons)

    except Exception as e:
        await event.respond(f"❌ Error loading tasks: {str(e)}")

    raise events.StopPropagation


@authorized_only
async def cmd_habits(event):
    """Show habit tracker summary"""
    try:
        habits = vault.list_active_habits()

        if not habits:
            await event.respond("📝 No active habits yet. Create one to get started!")
            raise events.StopPropagation

        response = "💪 **Habit Tracker**\n\n"

        # Sort by streak (descending)
        habits.sort(key=lambda h: h['metadata'].get('streak', 0), reverse=True)

        today = datetime.now(tz).strftime('%Y-%m-%d')

        response += "🔥 **Active Streaks**\n"
        for habit in habits:
            meta = habit['metadata']
            name = meta.get('name', 'Unknown')
            streak = meta.get('streak', 0)
            last_completed = meta.get('last_completed')

            # Check if completed today
            completed_today = last_completed == today
            status = "✅" if completed_today else "⏳"

            response += f"{status} {name}: {streak} days"
            if completed_today:
                response += " (today)"
            response += "\n"

        response += "\n"

        # Stats
        total_streaks = sum(h['metadata'].get('streak', 0) for h in habits)
        avg_streak = total_streaks / len(habits) if habits else 0

        response += "📊 **Stats**\n"
        response += f"Total habits: {len(habits)}\n"
        response += f"Average streak: {avg_streak:.1f} days\n"

        buttons = [
            [Button.inline("✅ Log Habit", b"log_habit")],
            [Button.inline("📈 View Details", b"habit_details")]
        ]

        await event.respond(response, buttons=buttons)

    except Exception as e:
        await event.respond(f"❌ Error loading habits: {str(e)}")

    raise events.StopPropagation


@authorized_only
async def cmd_tokens(event):
    """Show token balance"""
    try:
        ledger = vault.read_token_ledger()
        metadata = ledger['metadata']

        total = metadata.get('total_tokens', 0)
        today = metadata.get('tokens_today', 0)
        all_time = metadata.get('all_time_tokens', 0)

        response = "🪙 **Motivation Tokens**\n\n"
        response += f"💰 **Current Balance:** {total} tokens\n"
        response += f"📈 **Today's Earnings:** +{today} tokens\n\n"

        # Try to get today's breakdown
        try:
            daily = vault.read_daily_note()
            # Parse content for token transactions
            # This is simplified - you might want better parsing
            response += "**Today's Activities:**\n"
            response += "_See daily note for details_\n\n"
        except:
            pass

        response += f"**All Time:** {all_time} tokens\n\n"

        # Next milestone
        next_milestone = ((total // 50) + 1) * 50
        tokens_needed = next_milestone - total
        response += f"🎯 **Next Milestone**\n"
        response += f"{next_milestone} tokens"
        if tokens_needed > 0:
            response += f" ({tokens_needed} tokens away!)"

        buttons = [
            [Button.inline("📊 Token History", b"token_history")],
            [Button.inline("🎁 Redeem", b"redeem_tokens")]
        ]

        await event.respond(response, buttons=buttons)

    except Exception as e:
        await event.respond(f"❌ Error loading tokens: {str(e)}")

    raise events.StopPropagation


@authorized_only
async def cmd_help(event):
    """Show help message"""
    await event.respond(
        "📖 **Mazkir Bot Commands**\n\n"
        "**Quick Access**\n"
        "/day - Today's daily note\n"
        "/tasks - Your active tasks\n"
        "/habits - Habit tracker\n"
        "/tokens - Token balance\n\n"
        "**Natural Language**\n"
        "Just chat naturally! Examples:\n"
        "• \"I completed gym\"\n"
        "• \"Show my streaks\"\n"
        "• \"Create task: buy milk\"\n"
        "• \"What's my progress on learning ML?\"\n\n"
        "**Settings**\n"
        "/settings - Configure notifications\n\n"
        "Need help? Just ask!"
    )
    raise events.StopPropagation


# Natural language handler (catch-all)
@authorized_only
async def handle_message(event):
    """Handle natural language messages via Claude"""
    # Skip if it's a command
    if event.message.text.startswith('/'):
        return

    try:
        # Show typing indicator
        async with event.client.action(event.chat_id, 'typing'):
            # Get Claude's response
            response = claude.chat(event.message.text)

            # Send response
            await event.respond(response)

    except Exception as e:
        await event.respond(f"❌ Sorry, I encountered an error: {str(e)}")

    raise events.StopPropagation


# Export handlers with their patterns
def get_handlers():
    """Return list of (handler, event_builder) tuples"""
    return [
        (cmd_start, events.NewMessage(pattern='/start')),
        (cmd_day, events.NewMessage(pattern='/day')),
        (cmd_tasks, events.NewMessage(pattern='/tasks')),
        (cmd_habits, events.NewMessage(pattern='/habits')),
        (cmd_tokens, events.NewMessage(pattern='/tokens')),
        (cmd_help, events.NewMessage(pattern='/help')),
        (handle_message, events.NewMessage())  # Must be last (catch-all)
    ]
