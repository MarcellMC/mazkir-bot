"""Test script to verify setup is working correctly."""
import asyncio
import sys
from sqlalchemy import text

async def test_database():
    """Test database connection."""
    print("Testing database connection...")
    try:
        from src.database.connection import engine

        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✓ Database connected: PostgreSQL")

            # Check tables
            result = await conn.execute(text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            ))
            tables = [row[0] for row in result]
            print(f"✓ Tables found: {', '.join(tables)}")

            # Check pgvector extension
            result = await conn.execute(text(
                "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'"
            ))
            row = result.fetchone()
            if row:
                print(f"✓ pgvector extension: v{row[1]}")
            else:
                print("✗ pgvector extension not found")

        await engine.dispose()
        return True
    except Exception as e:
        print(f"✗ Database error: {e}")
        return False


async def test_ollama():
    """Test Ollama connection."""
    print("\nTesting Ollama connection...")
    try:
        import httpx
        from src.config import settings

        async with httpx.AsyncClient() as client:
            # Test if Ollama is running
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            if response.status_code == 200:
                models = response.json()
                model_names = [m['name'] for m in models.get('models', [])]
                print(f"✓ Ollama connected: {settings.ollama_base_url}")
                print(f"✓ Models available: {', '.join(model_names)}")

                # Check required models
                required_models = [settings.ollama_model, settings.ollama_embedding_model]
                for model in required_models:
                    model_base = model.split(':')[0]
                    if any(model_base in m for m in model_names):
                        print(f"✓ Required model '{model}' found")
                    else:
                        print(f"✗ Required model '{model}' not found")

                return True
            else:
                print(f"✗ Ollama returned status {response.status_code}")
                return False
    except Exception as e:
        print(f"✗ Ollama error: {e}")
        return False


async def test_config():
    """Test configuration."""
    print("\nTesting configuration...")
    try:
        from src.config import settings

        # Check required settings
        checks = [
            ("Telegram API ID", settings.telegram_api_id),
            ("Telegram API Hash", settings.telegram_api_hash),
            ("Telegram Phone", settings.telegram_phone),
            ("Database URL", settings.database_url),
            ("Ollama URL", settings.ollama_base_url),
        ]

        all_ok = True
        for name, value in checks:
            if value and str(value).strip() and "your_" not in str(value):
                print(f"✓ {name}: configured")
            else:
                print(f"✗ {name}: not configured")
                all_ok = False

        return all_ok
    except Exception as e:
        print(f"✗ Config error: {e}")
        return False


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Mazkir Bot - Setup Verification")
    print("=" * 60)

    results = []

    # Test configuration
    results.append(await test_config())

    # Test database
    results.append(await test_database())

    # Test Ollama
    results.append(await test_ollama())

    # Summary
    print("\n" + "=" * 60)
    if all(results):
        print("✓ All tests passed! Ready to run the bot.")
        print("\nTo start the bot, run:")
        print("  python -m src.main")
        return 0
    else:
        print("✗ Some tests failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
