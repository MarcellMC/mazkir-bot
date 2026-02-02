from pathlib import Path
from datetime import datetime
import frontmatter
import pytz
from typing import Dict, List, Optional


class VaultService:
    """Service for reading and writing to Obsidian vault"""

    def __init__(self, vault_path: Path, timezone: str = "Asia/Jerusalem"):
        self.vault_path = Path(vault_path)
        self.tz = pytz.timezone(timezone)

        # Verify vault exists
        if not self.vault_path.exists():
            raise FileNotFoundError(f"Vault not found: {vault_path}")

        # Verify AGENTS.md exists
        agents_md = self.vault_path / "AGENTS.md"
        if not agents_md.exists():
            raise FileNotFoundError("AGENTS.md not found in vault")

    def read_file(self, relative_path: str) -> Dict:
        """Read a markdown file and parse frontmatter

        Args:
            relative_path: Path relative to vault root (e.g., "10-daily/2026-01-07.md")

        Returns:
            Dict with 'metadata' (frontmatter) and 'content' (body)
        """
        file_path = self.vault_path / relative_path

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            post = frontmatter.load(f)

        return {
            'metadata': dict(post.metadata),
            'content': post.content,
            'path': relative_path
        }

    def write_file(self, relative_path: str, metadata: Dict, content: str):
        """Write a markdown file with frontmatter

        Args:
            relative_path: Path relative to vault root
            metadata: Dictionary of frontmatter fields
            content: Markdown body content
        """
        file_path = self.vault_path / relative_path

        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Always update 'updated' timestamp
        metadata['updated'] = datetime.now(self.tz).strftime('%Y-%m-%d')

        # Create frontmatter post
        post = frontmatter.Post(content, **metadata)

        # Write to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(frontmatter.dumps(post))

    def update_file(self, relative_path: str, metadata_updates: Dict):
        """Update frontmatter of existing file

        Args:
            relative_path: Path relative to vault root
            metadata_updates: Dictionary of fields to update
        """
        # Read existing
        file_data = self.read_file(relative_path)

        # Update metadata
        file_data['metadata'].update(metadata_updates)

        # Write back
        self.write_file(relative_path, file_data['metadata'], file_data['content'])

    def list_files(self, directory: str, pattern: str = "*.md") -> List[Path]:
        """List files in a directory

        Args:
            directory: Directory relative to vault root
            pattern: Glob pattern for files

        Returns:
            List of Path objects relative to vault root
        """
        dir_path = self.vault_path / directory

        if not dir_path.exists():
            return []

        files = list(dir_path.glob(pattern))

        # Return paths relative to vault root
        return [f.relative_to(self.vault_path) for f in files]

    # Convenience methods for common operations

    def get_daily_note_path(self, date: Optional[datetime] = None) -> str:
        """Get path to daily note for given date"""
        if date is None:
            date = datetime.now(self.tz)
        return f"10-daily/{date.strftime('%Y-%m-%d')}.md"

    def read_daily_note(self, date: Optional[datetime] = None) -> Dict:
        """Read daily note for given date"""
        path = self.get_daily_note_path(date)
        return self.read_file(path)

    def read_habit(self, habit_name: str) -> Dict:
        """Read habit file

        Args:
            habit_name: Name of habit (e.g., 'gym-workout')
        """
        return self.read_file(f"20-habits/{habit_name}.md")

    def update_habit(self, habit_name: str, updates: Dict) -> Dict:
        """Update habit file and return updated data"""
        path = f"20-habits/{habit_name}.md"
        self.update_file(path, updates)
        return self.read_file(path)

    def list_active_habits(self) -> List[Dict]:
        """Get all active habits with their data"""
        habit_files = self.list_files("20-habits")
        habits = []

        for file_path in habit_files:
            data = self.read_file(str(file_path))
            if data['metadata'].get('status') == 'active':
                habits.append(data)

        return habits

    def list_active_tasks(self) -> List[Dict]:
        """Get all active tasks"""
        task_files = self.list_files("40-tasks/active")
        tasks = []

        for file_path in task_files:
            data = self.read_file(str(file_path))
            tasks.append(data)

        # Sort by priority (high to low) then due_date
        def sort_key(task):
            from datetime import date
            priority = task['metadata'].get('priority', 3)
            due_date = task['metadata'].get('due_date')

            # Convert due_date to comparable format
            if due_date is None:
                due_date_sort = date(9999, 12, 31)  # Far future for tasks without due dates
            elif isinstance(due_date, str):
                from dateutil import parser
                due_date_sort = parser.parse(due_date).date()
            elif isinstance(due_date, date):
                due_date_sort = due_date
            else:
                due_date_sort = date(9999, 12, 31)

            return (-priority, due_date_sort)

        return sorted(tasks, key=sort_key)

    def read_token_ledger(self) -> Dict:
        """Read motivation tokens ledger"""
        return self.read_file("00-system/motivation-tokens.md")

    def update_tokens(self, tokens_earned: int, activity: str) -> Dict:
        """Award tokens and update ledger

        Args:
            tokens_earned: Amount of tokens to award
            activity: Description of activity

        Returns:
            Updated token data
        """
        # Read current ledger
        ledger = self.read_token_ledger()
        metadata = ledger['metadata']

        # Update totals
        old_total = metadata.get('total_tokens', 0)
        new_total = old_total + tokens_earned
        tokens_today = metadata.get('tokens_today', 0) + tokens_earned

        # Update metadata
        updates = {
            'total_tokens': new_total,
            'tokens_today': tokens_today,
            'all_time_tokens': metadata.get('all_time_tokens', 0) + tokens_earned
        }

        self.update_file("00-system/motivation-tokens.md", updates)

        # Add transaction to today's daily note
        now = datetime.now(self.tz)
        try:
            daily = self.read_daily_note()
            daily_metadata = daily['metadata']

            daily_updates = {
                'tokens_earned': daily_metadata.get('tokens_earned', 0) + tokens_earned,
                'tokens_total': new_total
            }

            self.update_file(self.get_daily_note_path(), daily_updates)
        except FileNotFoundError:
            # Daily note doesn't exist yet - that's okay
            pass

        return {
            'tokens_earned': tokens_earned,
            'old_total': old_total,
            'new_total': new_total,
            'activity': activity
        }
