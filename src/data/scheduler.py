import asyncio
from datetime import datetime, timezone
import pandas as pd
from loguru import logger

from src.data.parser import fetch_option_chain, parse_option_data, save_to_db
from src.db.models import SessionLocal, Ticker, SignalLog  # <- здесь SignalLog правильно
from src.signals.engine import generate_signals
from src.bot.bot import send_signal_to_subscribers

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
        chain, underlying_price, exp_date = fetch_option_chain(t.symbol)
        df = parse_option_data(chain, t.symbol, exp_date, underlying_price)
        save_to_db(df)

        # Генерация сигналов (теперь возвращает два DataFrame)
        signals_df, pcr_signals = generate_signals(df)
        
        # Сохранение обычных сигналов
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
                
                # Отправка сигнала подписчикам
                signal_data = {
                    'ticker': row['ticker'],
                    'option_type': row['option_type'],
                    'strike': row['strike'],
                    'expiration': row.get('expiration', ''),
                    'volume': row.get('volume', 0),
                    'volume_change': 0,
                    'implied_volatility': row.get('implied_volatility', 0),
                    'iv_change': 0,
                    'oi_change': row.get('open_interest', 0),
                    'last_price': row.get('last_price', 0),
                    'underlying_price': row.get('underlying_price', 0),
                    'signal_time': datetime.utcnow()
                }
                await send_signal_to_subscribers(signal_data)
                
            session.commit()
            session.close()
            logger.info(f"Option signals for {t.symbol} saved and sent.")
        
        # ДОБАВИТЬ: Сохранение PCR сигналов
        if not pcr_signals.empty:
            session = SessionLocal()
            for _, row in pcr_signals.iterrows():
                pcr_record = PutCallRatio(
                    ticker=row['ticker'],
                    call_volume=int(row['call_volume']),
                    put_volume=int(row['put_volume']),
                    call_oi=int(row['call_oi']),
                    put_oi=int(row['put_oi']),
                    pcr_volume=float(row['pcr_volume']),
                    pcr_oi=float(row['pcr_oi']),
                    signal_type=row['signal_type']
                )
                session.add(pcr_record)
                
                # Отправка PCR сигнала подписчикам
                await send_pcr_signal_to_subscribers(row)
                
            session.commit()
            session.close()
            logger.info(f"PCR signals for {t.symbol} saved and sent.")

async def start_scheduler():
    """Асинхронный планировщик для регулярного обновления данных"""
    logger.info("🚀 Scheduler started")
    while True:
        start_time = datetime.now(timezone.utc)
        logger.info(f"Обновление данных: {start_time}")
        await update_options_data()
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        sleep_time = max(UPDATE_INTERVAL_MIN * 60 - elapsed, 0)
        await asyncio.sleep(sleep_time)
