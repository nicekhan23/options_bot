from src.db.models import init_db

async def main():
    # Автоматически создаст таблицы при первом запуске
    init_db()
    
    # Запуск бота и scheduler
    await asyncio.gather(
        start_bot(),
        start_scheduler()
    )