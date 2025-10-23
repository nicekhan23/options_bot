import asyncio
from datetime import datetime
import pandas as pd
from loguru import logger

from src.data.parser import fetch_option_chain, parse_option_data, save_to_db
from src.db.models import SessionLocal, Ticker, SignalLog  # <- здесь SignalLog правильно
from src.signals.engine import generate_signals

logger.add("logs/scheduler.log", rotation="1 MB", retention="7 days", level="INFO")

UPDATE_INTERVAL_MIN = 10  # интервал обновления данных

async def update_options_data():
    """Получение и сохранение данных по всем тикерам"""
    session = SessionLocal()
    tickers = session.query(Ticker).all()
    session.close()

    if not tickers:
        logger.warning("Список тикеров пуст. Нет данных для обновления.")
        return

    for t in tickers:
        chain = fetch_option_chain(t.symbol)
        df = parse_option_data(chain, t.symbol)
        save_to_db(df)

        # Генерация сигналов
        signals_df = generate_signals(df)
        if not signals_df.empty:
            session = SessionLocal()
            for _, row in signals_df.iterrows():
                signal = SignalLog(
                    ticker=row['ticker'],
                    option_type=row['option_type'],
                    strike=row['strike'],
                    expiration=str(row.get('expiration', '')),
                    volume_change=row.get('volume', 0),
                    iv_change=row.get('implied_volatility', 0),
                    oi_change=row.get('open_interest', 0),
                    source="yfinance"
                )
                session.add(signal)
            session.commit()
            session.close()
            logger.info(f"Сигналы для {t.symbol} обновлены.")

async def start_scheduler():
    """Асинхронный планировщик для регулярного обновления данных"""
    logger.info("🚀 Scheduler started")
    while True:
        start_time = datetime.utcnow()
        logger.info(f"Обновление данных: {start_time}")
        await update_options_data()
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        sleep_time = max(UPDATE_INTERVAL_MIN * 60 - elapsed, 0)
        await asyncio.sleep(sleep_time)
