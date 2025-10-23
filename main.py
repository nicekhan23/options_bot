import asyncio
from src.db.models import init_db
from src.bot.bot import start_bot
from src.data.scheduler import start_scheduler

async def main():
    # Автоматически создаст таблицы при первом запуске
    init_db()
    
    # Запуск бота и scheduler
    await asyncio.gather(
        start_bot(),
        start_scheduler()
    )

if __name__ == "__main__":
    asyncio.run(main())