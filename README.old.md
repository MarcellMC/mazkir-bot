# Mazkir - Telegram Message Analyzer Bot

Mazkir is a Telegram bot that reads messages from channels (starting with Saved Messages) and uses LLMs to provide insights, analysis, and suggestions.

## Technology Stack

- **Language**: Python 3.10+
- **Telegram**: Telethon (MTProto API for channel access)
- **LLM**: LangChain with Claude API + Ollama (Llama)
- **Embeddings**: Ollama (nomic-embed-text)
- **Database**: PostgreSQL with pgvector extension
- **ORM**: SQLAlchemy 2.0 (async)
- **Migrations**: Alembic
- **Development**: Docker Compose

## Features (Planned)

- Read and analyze messages from Saved Messages
- Semantic search using vector embeddings
- LLM-powered insights and analysis
- Topic clustering and pattern detection
- Action item extraction
- Flexible LLM provider support (Claude, Llama)

## Prerequisites

- Python 3.10+
- Docker and Docker Compose
- Telegram API credentials (api_id and api_hash from https://my.telegram.org)
- Optional: Anthropic API key for Claude

## Setup

### 1. Clone and Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and fill in your credentials
# - Get Telegram API credentials from https://my.telegram.org
# - Optionally add Anthropic API key for Claude
```

### 3. Start Services

```bash
# Start PostgreSQL and Ollama
docker-compose up -d

# Pull Ollama models (first time only)
docker exec -it mazkir-ollama ollama pull llama3.1:8b
docker exec -it mazkir-ollama ollama pull nomic-embed-text
```

### 4. Initialize Database

```bash
# Create initial migration
alembic revision --autogenerate -m "Initial schema"

# Run migrations
alembic upgrade head
```

### 5. Run the Bot

```bash
python -m src.main
```

On first run, you'll be prompted to authenticate with your Telegram phone number.

## Project Structure

```
tg-mazkir/
├── src/
│   ├── bot/
│   │   ├── client.py          # Telethon client
│   │   └── handlers.py        # Command handlers
│   ├── services/
│   │   ├── llm_service.py     # LLM abstraction
│   │   └── embedding_service.py # Embeddings
│   ├── database/
│   │   ├── models.py          # SQLAlchemy models
│   │   ├── connection.py      # Database setup
│   │   └── repository.py      # Data access
│   ├── config.py              # Configuration
│   └── main.py                # Entry point
├── alembic/                   # Database migrations
├── docker/                    # Docker configs
├── docker-compose.yml
└── requirements.txt
```

## Usage

### Available Commands

- `/start` - Start the bot
- `/help` - Show help message
- `/analyze` - Analyze recent messages (coming soon)

## Development

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

### Switching LLM Providers

The bot supports multiple LLM providers. Edit `src/services/llm_service.py` or pass the provider when initializing:

```python
from src.services.llm_service import LLMService

# Use Ollama (free, local)
llm = LLMService(provider="ollama")

# Use Claude (requires API key)
llm = LLMService(provider="claude")
```

## License

MIT
