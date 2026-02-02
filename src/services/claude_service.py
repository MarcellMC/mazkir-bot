import anthropic
from datetime import datetime
import pytz
from typing import List, Dict


class ClaudeService:
    """Service for interacting with Claude API"""

    def __init__(self, api_key: str, vault_path: str, timezone: str = "Asia/Jerusalem"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.vault_path = vault_path
        self.tz = pytz.timezone(timezone)

        # Read AGENTS.md from vault for context
        agents_md_path = f"{vault_path}/AGENTS.md"
        try:
            with open(agents_md_path, 'r', encoding='utf-8') as f:
                self.vault_docs = f.read()
        except FileNotFoundError:
            self.vault_docs = "AGENTS.md not found"

    def build_system_prompt(self, context: Dict = None) -> str:
        """Build system prompt with vault context"""
        now = datetime.now(self.tz)

        base_prompt = f"""You are Marc's Personal AI Assistant with access to his Obsidian vault.

Current date: {now.strftime('%Y-%m-%d')}
Current time: {now.strftime('%H:%M')}
Day of week: {now.strftime('%A')}
Timezone: {self.tz.zone}

Vault location: {self.vault_path}

# Vault Documentation

{self.vault_docs}

# Your Capabilities

You can help Marc with:
- Tracking habits and building streaks
- Managing tasks and goals
- Awarding motivation tokens
- Creating and updating daily notes
- Providing progress reports and insights
- Answering questions about his vault data

# Important Guidelines

1. Be encouraging and supportive
2. Use emojis appropriately (💪🎯📖🧘🪙)
3. Be concise - Marc is busy
4. Show streaks, totals, and progress
5. Suggest next actions
6. NEVER delete user data without explicit confirmation
7. ALWAYS update the 'updated' field when modifying files

When Marc completes an activity:
1. Identify the type (habit/task/goal)
2. Calculate tokens earned (see token values in AGENTS.md)
3. Update the relevant files
4. Respond with encouragement + stats
"""

        if context:
            base_prompt += f"\n\n# Additional Context\n\n{context}\n"

        return base_prompt

    def chat(self, message: str, context: Dict = None, model: str = "claude-sonnet-4-20250514", max_tokens: int = 4000) -> str:
        """Send message to Claude and get response

        Args:
            message: User's message
            context: Optional context dictionary
            model: Claude model to use
            max_tokens: Maximum tokens in response

        Returns:
            Claude's response as text
        """
        system_prompt = self.build_system_prompt(context)

        response = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": message
            }]
        )

        return response.content[0].text

    def process_completion(self, activity: str) -> Dict:
        """Process activity completion and determine actions

        Args:
            activity: Description of completed activity

        Returns:
            Dict with 'response' (text) and 'actions' (list of dicts)
        """
        # This is a simplified version
        # In practice, Claude would parse the activity and return structured data

        message = f"I completed: {activity}"
        response = self.chat(message)

        return {
            'response': response,
            'actions': []  # Parse actions from response if needed
        }
