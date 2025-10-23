import pandas as pd
from datetime import datetime, timedelta, timezone
from loguru import logger
from src.db.models import Settings

logger.add("logs/signals.log", rotation="1 MB", retention="7 days", level="INFO")

def detect_volume_spike(df: pd.DataFrame, k: float = 3.0):
    """
    Выделяет опционы с объёмом > k * среднего объёма
    df: DataFrame с колонками ['volume', 'ticker', 'option_type', 'strike', 'expiration']
    k: множитель для всплеска объёма
    """
    if df.empty or 'volume' not in df.columns:
        return pd.DataFrame()

    df['avg_volume'] = df.groupby('ticker')['volume'].transform('mean')
    df['volume_spike'] = df['volume'] > k * df['avg_volume']
    spikes = df[df['volume_spike']]
    logger.info(f"Volume spikes detected: {len(spikes)}")
    return spikes.drop(columns=['avg_volume', 'volume_spike'])

def detect_iv_increase(df: pd.DataFrame, threshold: float = 0.1):
    """
    Выделяет опционы с ростом implied volatility выше threshold
    df: DataFrame с колонками ['implied_volatility', 'ticker', 'option_type', 'strike', 'expiration']
    threshold: минимальный относительный рост IV (например, 0.1 = 10%)
    """
    if df.empty or 'implied_volatility' not in df.columns:
        return pd.DataFrame()

    df['avg_iv'] = df.groupby('ticker')['implied_volatility'].transform('mean')
    df['iv_increase'] = df['implied_volatility'] > (1 + threshold) * df['avg_iv']
    iv_alerts = df[df['iv_increase']]
    logger.info(f"IV increases detected: {len(iv_alerts)}")
    return iv_alerts.drop(columns=['avg_iv', 'iv_increase'])

def filter_by_expiration(df: pd.DataFrame, days: int = 7):
    """
    Фильтрует опционы по ближайшей дате экспирации
    df: DataFrame с колонкой 'expiration' (строка YYYY-MM-DD или datetime)
    days: максимальное количество дней до экспирации
    """
    if df.empty or 'expiration' not in df.columns:
        return pd.DataFrame()

    today = datetime.now(timezone.utc)()
    df['expiration_date'] = pd.to_datetime(df['expiration'], errors='coerce')
    filtered = df[df['expiration_date'] <= today + timedelta(days=days)]
    logger.info(f"Options filtered by expiration <= {days} days: {len(filtered)}")
    return filtered.drop(columns=['expiration_date'])

def get_setting(session, key: str, default: float):
    """Получить значение настройки из БД"""
    setting = session.query(Settings).filter(Settings.key == key).first()
    return setting.value if setting else default

def set_setting(session, key: str, value: float):
    """Сохранить значение настройки в БД"""
    setting = session.query(Settings).filter(Settings.key == key).first()
    if setting:
        setting.value = value
        setting.updated_at = datetime.now(timezone.utc)()
    else:
        setting = Settings(key=key, value=value)
        session.add(setting)
    session.commit()
    
def calculate_put_call_ratio(df: pd.DataFrame):
    """
    Рассчитывает Put/Call Ratio по объёму и открытому интересу
    Высокий PCR (>1.0) = медвежий сигнал
    Низкий PCR (<0.7) = бычий сигнал
    """
    if df.empty:
        return pd.DataFrame()
    
    grouped = df.groupby(['ticker', 'option_type']).agg({
        'volume': 'sum',
        'open_interest': 'sum'
    }).reset_index()
    
    results = []
    
    for ticker in grouped['ticker'].unique():
        ticker_data = grouped[grouped['ticker'] == ticker]
        
        call_data = ticker_data[ticker_data['option_type'] == 'CALL']
        put_data = ticker_data[ticker_data['option_type'] == 'PUT']
        
        call_volume = call_data['volume'].sum() if not call_data.empty else 0
        put_volume = put_data['volume'].sum() if not put_data.empty else 0
        
        call_oi = call_data['open_interest'].sum() if not call_data.empty else 0
        put_oi = put_data['open_interest'].sum() if not put_data.empty else 0
        
        # Расчёт Put/Call Ratio
        pcr_volume = put_volume / call_volume if call_volume > 0 else 0
        pcr_oi = put_oi / call_oi if call_oi > 0 else 0
        
        results.append({
            'ticker': ticker,
            'call_volume': call_volume,
            'put_volume': put_volume,
            'call_oi': call_oi,
            'put_oi': put_oi,
            'pcr_volume': pcr_volume,
            'pcr_oi': pcr_oi,
            'total_volume': call_volume + put_volume,
            'total_oi': call_oi + put_oi
        })
    
    pcr_df = pd.DataFrame(results)
    logger.info(f"Put/Call ratios calculated for {len(pcr_df)} tickers")
    return pcr_df

def detect_unusual_pcr(pcr_df: pd.DataFrame, bearish_threshold=1.5, bullish_threshold=0.5):
    """
    Выявляет необычные значения Put/Call Ratio
    bearish_threshold: PCR выше этого значения = сильный медвежий сигнал
    bullish_threshold: PCR ниже этого значения = сильный бычий сигнал
    """
    if pcr_df.empty:
        return pd.DataFrame()
    
    unusual = pcr_df[
        (pcr_df['pcr_volume'] > bearish_threshold) | 
        (pcr_df['pcr_volume'] < bullish_threshold)
    ].copy()
    
    # Определение типа сигнала
    unusual['signal_type'] = unusual['pcr_volume'].apply(
        lambda x: 'BEARISH' if x > bearish_threshold else 'BULLISH'
    )
    
    logger.info(f"Unusual PCR detected: {len(unusual)} signals")
    return unusual

def generate_signals(df: pd.DataFrame, volume_k=3, iv_threshold=0.1, exp_days=7):
    """
    Основная функция: объединяет все фильтры и возвращает итоговые сигналы
    """
    if df.empty:
        logger.info("No data to generate signals")
        return pd.DataFrame(), pd.DataFrame()  # Возвращаем два DataFrame

    # Существующие сигналы
    volume_spikes = detect_volume_spike(df, k=volume_k)
    iv_alerts = detect_iv_increase(df, threshold=iv_threshold)
    combined = pd.concat([volume_spikes, iv_alerts]).drop_duplicates()
    final_signals = filter_by_expiration(combined, days=exp_days)
    
    # Новые сигналы Put/Call Ratio
    pcr_data = calculate_put_call_ratio(df)
    pcr_signals = detect_unusual_pcr(pcr_data)
    
    logger.info(f"Total option signals: {len(final_signals)}, PCR signals: {len(pcr_signals)}")
    return final_signals, pcr_signals
