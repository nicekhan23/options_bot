import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from loguru import logger
from src.db.models import SessionLocal, Ticker, SignalLog

import os
from dotenv import load_dotenv

# Загрузка токена из .env
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Пожалуйста, укажите TELEGRAM_BOT_TOKEN в файле .env")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

logger.add("logs/bot.log", rotation="1 MB", retention="7 days", level="INFO")

# === Команда /start ===
@dp.message(Command(commands=["start"]))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я Options Signal Bot.\n\n"
        "Доступные команды:\n"
        "/signals — показать последние торговые сигналы\n"
        "/watchlist — показать текущие тикеры\n"
        "/add [TICKER] — добавить тикер\n"
        "/remove [TICKER] — удалить тикер"
    )

# === Команда /watchlist ===
@dp.message(Command(commands=["watchlist"]))
async def cmd_watchlist(message: types.Message):
    session = SessionLocal()
    tickers = session.query(Ticker).all()
    session.close()
    if tickers:
        text = "📌 Отслеживаемые тикеры:\n" + "\n".join([t.symbol for t in tickers])
    else:
        text = "Список тикеров пуст."
    await message.answer(text)

# === Команда /add [TICKER] ===
@dp.message(Command(commands=["add"]))
async def cmd_add(message: types.Message):
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /add [TICKER]")
        return
    symbol = args[1].upper()
    session = SessionLocal()
    existing = session.query(Ticker).filter(Ticker.symbol == symbol).first()
    if existing:
        await message.answer(f"{symbol} уже в списке.")
    else:
        new_ticker = Ticker(symbol=symbol)
        session.add(new_ticker)
        session.commit()
        await message.answer(f"✅ {symbol} добавлен в список тикеров.")
    session.close()

# === Команда /remove [TICKER] ===
@dp.message(Command(commands=["remove"]))
async def cmd_remove(message: types.Message):
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /remove [TICKER]")
        return
    symbol = args[1].upper()
    session = SessionLocal()
    existing = session.query(Ticker).filter(Ticker.symbol == symbol).first()
    if existing:
        session.delete(existing)
        session.commit()
        await message.answer(f"❌ {symbol} удалён из списка тикеров.")
    else:
        await message.answer(f"{symbol} не найден в списке.")
    session.close()

# === Команда /signals ===
@dp.message(Command(commands=["signals"]))
async def cmd_signals(message: types.Message):
    session = SessionLocal()
    signals = session.query(SignalLog).order_by(SignalLog.signal_time.desc()).limit(10).all()
    session.close()
    if not signals:
        await message.answer("⚠️ Сигналов пока нет.")
        return

    text_lines = []
    for s in signals:
        text_lines.append(
            f"🚨 {s.ticker} | {s.option_type} | Strike: {s.strike} | Exp: {s.expiration}\n"
            f"Volume change: {s.volume_change} | IV change: {s.iv_change}\n"
            f"OI change: {s.oi_change}\n"
            f"Time: {s.signal_time.strftime('%Y-%m-%d %H:%M')}\n"
            f"Source: {s.source}"
        )
    await message.answer("\n\n".join(text_lines))

# === Запуск бота ===
async def start_bot():
    logger.info("🚀 Telegram bot started")
    await dp.start_polling(bot)

# === Точка входа для main.py ===
if __name__ == "__main__":
    asyncio.run(start_bot())
