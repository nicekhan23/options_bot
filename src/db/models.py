from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone

# База SQLite
DATABASE_URL = "sqlite:///./options_data.db"

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()

# Таблица для отслеживаемых тикеров
class Ticker(Base):
    __tablename__ = "tickers"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True)
    added_at = Column(DateTime, default=datetime.now(timezone.utc))

# Таблица для данных по опционам
class OptionData(Base):
    __tablename__ = "options_data"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    option_type = Column(String)  # Call / Put
    strike = Column(Float)
    expiration = Column(String)
    last_price = Column(Float)
    bid = Column(Float)
    ask = Column(Float)
    implied_volatility = Column(Float)
    volume = Column(Integer)
    open_interest = Column(Integer)
    underlying_price = Column(Float)
    updated_at = Column(DateTime, default=datetime.now(timezone.utc))

# Таблица для логов сигналов
class SignalLog(Base):
    __tablename__ = "signals_log"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String)
    option_type = Column(String)
    strike = Column(Float)
    expiration = Column(String)
    volume_change = Column(Float)
    iv_change = Column(Float)
    oi_change = Column(Integer)
    signal_time = Column(DateTime, default=datetime.now(timezone.utc))
    source = Column(String)
    
# Добавить после SignalLog
class PutCallRatio(Base):
    __tablename__ = "put_call_ratios"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    call_volume = Column(Integer)
    put_volume = Column(Integer)
    call_oi = Column(Integer)
    put_oi = Column(Integer)
    pcr_volume = Column(Float)  # Put/Call Ratio по объёму
    pcr_oi = Column(Float)  # Put/Call Ratio по открытому интересу
    signal_type = Column(String)  # BULLISH / BEARISH / NEUTRAL
    calculated_at = Column(DateTime, default=datetime.now(timezone.utc))   
    
# Добавить новую таблицу после SignalLog
class Settings(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    value = Column(Float)
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
# Добавить после таблицы Settings
class Subscriber(Base):
    __tablename__ = "subscribers"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, index=True)  # Telegram user ID
    username = Column(String, nullable=True)
    subscribed = Column(Boolean, default=True)
    subscribed_at = Column(DateTime, default=datetime.now(timezone.utc))
    
class OptionSnapshot(Base):
    __tablename__ = "option_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    option_type = Column(String)
    strike = Column(Float)
    expiration = Column(String)
    volume = Column(Integer)
    open_interest = Column(Integer)
    implied_volatility = Column(Float)
    last_price = Column(Float)
    snapshot_time = Column(DateTime, default=datetime.now(timezone.utc), index=True)

# Функция для создания всех таблиц
def init_db():
    Base.metadata.create_all(bind=engine)
    print("✅ База данных и таблицы созданы")
