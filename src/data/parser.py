import yfinance as yf
import pandas as pd
from loguru import logger
from datetime import datetime
from src.db.models import SessionLocal, OptionData

logger.add("logs/parser.log", rotation="1 MB", retention="7 days", level="INFO")

def fetch_option_chain(ticker_symbol: str):
    """Получить данные по опционам для одного тикера"""
    try:
        ticker = yf.Ticker(ticker_symbol)
        expirations = ticker.options
        if not expirations:
            logger.warning(f"Нет доступных дат экспирации для {ticker_symbol}")
            return None
        # Берём ближайшую дату экспирации
        opt_chain = ticker.option_chain(expirations[0])
        logger.info(f"Опционы для {ticker_symbol} получены (экспирация {expirations[0]})")
        return opt_chain
    except Exception as e:
        logger.error(f"Ошибка при получении опционов {ticker_symbol}: {e}")
        return None

def parse_option_data(opt_chain, ticker_symbol: str):
    """Преобразует цепочку опционов в DataFrame"""
    if opt_chain is None:
        return pd.DataFrame()
    
    calls = opt_chain.calls.copy()
    puts = opt_chain.puts.copy()
    
    calls['option_type'] = 'CALL'
    puts['option_type'] = 'PUT'
    
    df = pd.concat([calls, puts], ignore_index=True)
    
    # Добавляем тикер и время обновления
    df['ticker'] = ticker_symbol
    df['updated_at'] = datetime.utcnow()
    
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
                underlying_price=row.get('underlyingPrice', None),
                updated_at=row['updated_at']
            )
            session.merge(option)  # merge обновляет или добавляет
        session.commit()
        logger.info(f"Сохранено {len(df)} записей в базу")
    except Exception as e:
        session.rollback()
        logger.error(f"Ошибка при сохранении в базу: {e}")
    finally:
        session.close()

# === Пример использования ===
if __name__ == "__main__":
    ticker_list = ["AAPL", "TSLA", "NVDA"]
    for ticker in ticker_list:
        chain = fetch_option_chain(ticker)
        df = parse_option_data(chain, ticker)
        save_to_db(df)
