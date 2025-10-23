import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Database
DATABASE_URL = "sqlite:///./options_data.db"

# Scheduler settings
UPDATE_INTERVAL_MIN = 10  # интервал обновления данных в минутах

# Signal detection thresholds (defaults)
DEFAULT_VOLUME_SPIKE_K = 3.0
DEFAULT_IV_THRESHOLD = 0.1  # 10%
DEFAULT_EXPIRATION_DAYS = 7

# Put/Call Ratio thresholds
PCR_BEARISH_THRESHOLD = 1.5
PCR_BULLISH_THRESHOLD = 0.5

# API settings
YFINANCE_RETRY_ATTEMPTS = 3
YFINANCE_RETRY_DELAY = 5  # seconds
REQUEST_TIMEOUT = 10  # seconds

# Logging
LOG_ROTATION = "1 MB"
LOG_RETENTION = "7 days"