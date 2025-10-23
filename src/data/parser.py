import yfinance as yf
import pandas as pd
from loguru import logger
from datetime import datetime, timezone
import time
from src.db.models import SessionLocal, OptionData, OptionSnapshot
import config

logger.add("logs/parser.log", rotation=config.LOG_ROTATION, retention=config.LOG_RETENTION, level="INFO")

def fetch_option_chain(ticker_symbol: str, retry_count=0):
    """Получение цепочки опционов с retry логикой"""
    try:
        ticker = yf.Ticker(ticker_symbol)
        expirations = ticker.options
        
        if not expirations:
            logger.warning(f"Нет доступных дат экспирации для {ticker_symbol}")
            return None, None, None
        
        opt_chain = ticker.option_chain(expirations[0])
        current_price = ticker.info.get('regularMarketPrice', ticker.info.get('currentPrice', None))
        
        logger.info(f"Опционы для {ticker_symbol} получены (экспирация {expirations[0]})")
        return opt_chain, current_price, expirations[0]
        
    except Exception as e:
        logger.error(f"Ошибка при получении опционов {ticker_symbol}: {e}")
        
        # Retry логика
        if retry_count < config.YFINANCE_RETRY_ATTEMPTS:
            logger.info(f"Повторная попытка {retry_count + 1}/{config.YFINANCE_RETRY_ATTEMPTS} для {ticker_symbol}")
            time.sleep(config.YFINANCE_RETRY_DELAY)
            return fetch_option_chain(ticker_symbol, retry_count + 1)
        
        return None, None, None

def parse_option_data(opt_chain, ticker_symbol: str, expiration_date: str, underlying_price: float):
    """Преобразует цепочку опционов в DataFrame"""
    if opt_chain is None:
        return pd.DataFrame()
    
    calls = opt_chain.calls.copy()
    puts = opt_chain.puts.copy()
    
    calls['option_type'] = 'CALL'
    puts['option_type'] = 'PUT'
    
    df = pd.concat([calls, puts], ignore_index=True)
    
    # Добавляем метаданные
    df['ticker'] = ticker_symbol
    df['expiration'] = expiration_date
    df['updated_at'] = datetime.now(timezone.utc)
    df['underlying_price'] = underlying_price
    
    # Приведение столбцов к стандартному виду
    df = df.rename(columns={
        "contractSymbol": "contract_symbol",
        "strike": "strike",
        "lastPrice": "last_price",
        "bid": "bid",
        "ask": "ask",
        "impliedVolatility": "implied_volatility",
        "volume": "volume",
        "openInterest": "open_interest",
        "lastTradeDate": "last_trade_date",
        "inTheMoney": "in_the_money"
    })
    
    return df

def save_to_db(df: pd.DataFrame):
    """Сохраняет DataFrame с опционами в базу SQLite"""
    if df.empty:
        logger.warning("DataFrame пустой, нечего сохранять")
        return
    
    session = SessionLocal()
    try:
        for _, row in df.iterrows():
            # Сохранение в основную таблицу
            option = OptionData(
                ticker=row['ticker'],
                option_type=row['option_type'],
                strike=row['strike'],
                expiration=str(row.get('expiration', '')),
                last_price=row.get('last_price', None),
                bid=row.get('bid', None),
                ask=row.get('ask', None),
                implied_volatility=row.get('implied_volatility', None),
                volume=row.get('volume', None),
                open_interest=row.get('open_interest', None),
                underlying_price=row.get('underlying_price', None),
                updated_at=row['updated_at']
            )
            session.merge(option)
            
            # Сохранение снимка для истории
            snapshot = OptionSnapshot(
                ticker=row['ticker'],
                option_type=row['option_type'],
                strike=row['strike'],
                expiration=str(row.get('expiration', '')),
                volume=row.get('volume', None),
                open_interest=row.get('open_interest', None),
                implied_volatility=row.get('implied_volatility', None),
                last_price=row.get('last_price', None),
                snapshot_time=row['updated_at']
            )
            session.add(snapshot)
            
        session.commit()
        logger.info(f"Сохранено {len(df)} записей в базу (данные + снимки)")
    except Exception as e:
        session.rollback()
        logger.error(f"Ошибка при сохранении в базу: {e}")
    finally:
        session.close()