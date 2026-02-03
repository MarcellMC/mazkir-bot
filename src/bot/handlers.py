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
    import logging
    logger = logging.getLogger(__name__)

    try:
        tasks = vault.list_active_tasks()

        logger.info(f"Found {len(tasks)} tasks in 40-tasks/active/")
        for task in tasks:
            logger.info(f"  - Task: {task['path']}, priority: {task['metadata'].get('priority', 3)}")

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
            import re
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

                        # Remove markdown links: [text](url) -> text
                        name = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', name)

                        # Remove other markdown formatting
                        name = name.replace('**', '').replace('*', '').replace('`', '')

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
    import logging
    logger = logging.getLogger(__name__)

    # Skip if it's a command
    if event.message.text.startswith('/'):
        return

    try:
        # Show typing indicator
        async with event.client.action(event.chat_id, 'typing'):
            user_message = event.message.text

            # Get list of habits for context
            habits = vault.list_active_habits()
            habit_names = [h['metadata'].get('name', 'Unknown') for h in habits]

            # Parse user intent
            logger.info(f"Parsing intent for message: {user_message}")
            intent_result = claude.parse_intent(user_message, habit_names)
            logger.info(f"Intent: {intent_result.get('intent')}, Data: {intent_result.get('data')}")

            intent = intent_result.get('intent')
            data = intent_result.get('data', {})

            # Handle different intents
            if intent == 'HABIT_COMPLETION':
                response = await handle_habit_completion(data)
            elif intent == 'TASK_CREATION':
                response = await handle_task_creation(data)
            elif intent == 'QUERY':
                response = await handle_query(data, user_message)
            else:
                # General chat - just use Claude
                response = claude.chat(user_message)

            # Send response
            await event.respond(response)

    except Exception as e:
        logger.error(f"Error in natural language handler: {e}", exc_info=True)
        await event.respond(f"❌ Sorry, I encountered an error: {str(e)}")

    raise events.StopPropagation


async def handle_habit_completion(data: dict) -> str:
    """Handle habit completion intent"""
    import logging
    logger = logging.getLogger(__name__)

    habit_name = data.get('habit_name', '').lower()
    confidence = data.get('confidence', 'low')

    logger.info(f"Habit completion: {habit_name}, confidence: {confidence}")

    if not habit_name:
        return "I'm not sure which habit you completed. Could you be more specific?"

    # Find matching habit
    habits = vault.list_active_habits()
    matched_habit = None

    for habit in habits:
        h_name = habit['metadata'].get('name', '').lower()
        if habit_name in h_name or h_name in habit_name:
            matched_habit = habit
            break

    if not matched_habit:
        return f"❌ I couldn't find a habit matching '{habit_name}'. Available habits: {', '.join([h['metadata'].get('name') for h in habits])}"

    # Get habit details
    habit_meta = matched_habit['metadata']
    habit_full_name = habit_meta.get('name')
    current_streak = habit_meta.get('streak', 0)
    tokens_per_completion = habit_meta.get('tokens_per_completion', 5)

    # Update habit
    today = datetime.now(tz).strftime('%Y-%m-%d')
    last_completed = habit_meta.get('last_completed')

    # Check if already completed today
    if last_completed == today:
        return f"✅ You already completed **{habit_full_name}** today! Current streak: {current_streak} days"

    # Update streak
    new_streak = current_streak + 1

    # Update habit file
    habit_path = matched_habit['path']
    vault.update_file(habit_path, {
        'streak': new_streak,
        'last_completed': today,
        'longest_streak': max(habit_meta.get('longest_streak', 0), new_streak)
    })

    # Award tokens
    token_result = vault.update_tokens(tokens_per_completion, f"Completed {habit_full_name}")

    # Build response
    response = f"💪 Excellent! **{habit_full_name}** completed!\n\n"
    response += f"🔥 Streak: {current_streak} → **{new_streak} days**\n"
    response += f"🪙 Tokens: +{tokens_per_completion}\n"
    response += f"💰 New balance: **{token_result['new_total']} tokens**\n\n"

    # Encouragement based on streak milestones
    if new_streak == 7:
        response += "🎉 One week streak! Keep it up!"
    elif new_streak == 30:
        response += "🏆 30 days! You're building a solid habit!"
    elif new_streak == 100:
        response += "⭐ 100 days! Legendary!"
    elif new_streak % 10 == 0:
        response += f"✨ {new_streak} days! You're on fire!"

    return response


async def handle_task_creation(data: dict) -> str:
    """Handle task creation intent"""
    task_description = data.get('task_description', '').strip()
    priority = data.get('priority', 3)

    if not task_description:
        return "I'm not sure what task you want to create. Please describe the task."

    # Create task file
    # Sanitize filename
    import re
    filename = re.sub(r'[^\w\s-]', '', task_description)
    filename = re.sub(r'[-\s]+', '-', filename)
    filename = filename[:50]  # Limit length

    task_path = f"40-tasks/active/{filename}.md"
    today = datetime.now(tz).strftime('%Y-%m-%d')

    metadata = {
        'type': 'task',
        'status': 'active',
        'priority': priority,
        'category': 'personal',
        'tags': ['task'],
        'created': today,
        'updated': today
    }

    content = f"# {task_description}\n\n"

    vault.write_file(task_path, metadata, content)

    priority_label = {5: "🔴 High", 4: "🔴 High", 3: "🟡 Medium", 2: "🟢 Low", 1: "🟢 Low"}.get(priority, "🟡 Medium")

    return f"✅ Task created: **{task_description}**\n\n" \
           f"Priority: {priority_label}\n" \
           f"Status: Active\n\n" \
           f"Use /tasks to view all active tasks."


async def handle_query(data: dict, original_message: str) -> str:
    """Handle query intent"""
    query_type = data.get('query_type', 'general')

    if query_type == 'streaks':
        habits = vault.list_active_habits()
        habits.sort(key=lambda h: h['metadata'].get('streak', 0), reverse=True)

        response = "🔥 **Your Habit Streaks**\n\n"
        for habit in habits[:10]:  # Top 10
            meta = habit['metadata']
            name = meta.get('name')
            streak = meta.get('streak', 0)
            longest = meta.get('longest_streak', 0)
            response += f"• **{name}**: {streak} days (best: {longest})\n"

        return response

    elif query_type == 'tokens':
        ledger = vault.read_token_ledger()
        meta = ledger['metadata']
        return f"🪙 **Token Balance**\n\n" \
               f"💰 Current: **{meta.get('total_tokens', 0)} tokens**\n" \
               f"📈 Today: +{meta.get('tokens_today', 0)}\n" \
               f"⭐ All time: {meta.get('all_time_tokens', 0)}"

    else:
        # General query - use Claude
        return claude.chat(original_message)


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
