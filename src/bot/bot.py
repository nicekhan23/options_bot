import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from loguru import logger
from src.db.models import SessionLocal, Ticker, SignalLog
from src.db.models import Subscriber
from src.db.models import PutCallRatio


import os
from dotenv import load_dotenv

class SettingsState(StatesGroup):
    waiting_for_value = State()

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

# Добавить после определения dp
async def send_signal_to_subscribers(signal_data: dict):
    """Отправляет сигнал всем подписчикам"""
    session = SessionLocal()
    subscribers = session.query(Subscriber).filter(Subscriber.subscribed == True).all()
    session.close()
    
    if not subscribers:
        logger.info("No active subscribers")
        return
    
    # Форматирование сигнала
    text = (
        f"🚨 <b>Unusual Options Activity Detected</b>\n\n"
        f"<b>Ticker:</b> {signal_data['ticker']}\n"
        f"<b>Type:</b> {signal_data['option_type']} | <b>Strike:</b> {signal_data['strike']} | <b>Exp:</b> {signal_data['expiration']}\n"
        f"<b>Volume:</b> {signal_data.get('volume', 'N/A')} (+{signal_data.get('volume_change', 0):.1f}%)\n"
        f"<b>IV:</b> {signal_data.get('implied_volatility', 0)*100:.1f}% (↑{signal_data.get('iv_change', 0)*100:.1f}%)\n"
        f"<b>OI Change:</b> +{signal_data.get('oi_change', 0)}\n"
        f"<b>Last Price:</b> ${signal_data.get('last_price', 0):.2f}\n"
        f"<b>Underlying:</b> ${signal_data.get('underlying_price', 0):.2f}\n"
        f"<b>Time:</b> {signal_data.get('signal_time', datetime.utcnow()).strftime('%Y-%m-%d %H:%M')} UTC\n\n"
        f"📊 <a href='https://finance.yahoo.com/quote/{signal_data['ticker']}/options'>View on Yahoo Finance</a>"
    )
    
    # Отправка всем подписчикам
    for sub in subscribers:
        try:
            await bot.send_message(sub.user_id, text, disable_web_page_preview=True)
            logger.info(f"Signal sent to user {sub.user_id}")
        except Exception as e:
            logger.error(f"Failed to send signal to user {sub.user_id}: {e}")
            # Если пользователь заблокировал бота, отписываем его
            if "bot was blocked" in str(e).lower():
                session = SessionLocal()
                subscriber = session.query(Subscriber).filter(Subscriber.user_id == sub.user_id).first()
                if subscriber:
                    subscriber.subscribed = False
                    session.commit()
                session.close()

# === Команда /start ===
@dp.message(Command(commands=["start"]))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я Options Signal Bot.\n\n"
        "Доступные команды:\n"
        "/subscribe — подписаться на автоматические сигналы\n"
        "/unsubscribe — отписаться от сигналов\n"
        "/signals — показать последние торговые сигналы\n"
        "/pcr — показать Put/Call Ratios\n"
        "/watchlist — показать текущие тикеры\n"
        "/add [TICKER] — добавить тикер\n"
        "/remove [TICKER] — удалить тикер\n"
        "/settings — настройки фильтров"
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
    
@dp.message(Command(commands=["settings"]))
async def cmd_settings(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔊 Volume Spike (k)", callback_data="setting_volume_k")],
        [InlineKeyboardButton(text="📈 IV Threshold (%)", callback_data="setting_iv_threshold")],
        [InlineKeyboardButton(text="📅 Expiration Days", callback_data="setting_exp_days")],
        [InlineKeyboardButton(text="✅ Current Settings", callback_data="setting_show")]
    ])
    await message.answer(
        "⚙️ <b>Настройки фильтров сигналов</b>\n\n"
        "Выберите параметр для изменения:",
        reply_markup=keyboard
    )
    
@dp.message(Command(commands=["pcr"]))
async def cmd_pcr(message: types.Message):
    """Показать текущие Put/Call Ratio для всех тикеров"""
    session = SessionLocal()
    pcr_data = session.query(PutCallRatio).order_by(PutCallRatio.calculated_at.desc()).limit(10).all()
    session.close()
    
    if not pcr_data:
        await message.answer("⚠️ Данных по Put/Call Ratio пока нет.")
        return
    
    text_lines = ["📊 <b>Put/Call Ratios</b>\n"]
    
    for pcr in pcr_data:
        emoji = "🐻" if pcr.signal_type == 'BEARISH' else "🐂" if pcr.signal_type == 'BULLISH' else "➖"
        text_lines.append(
            f"{emoji} <b>{pcr.ticker}</b> | {pcr.signal_type}\n"
            f"  Volume PCR: {pcr.pcr_volume:.2f} (Calls: {pcr.call_volume:,} | Puts: {pcr.put_volume:,})\n"
            f"  OI PCR: {pcr.pcr_oi:.2f} (Calls: {pcr.call_oi:,} | Puts: {pcr.put_oi:,})\n"
            f"  Time: {pcr.calculated_at.strftime('%Y-%m-%d %H:%M')}\n"
        )
    
    await message.answer("\n".join(text_lines))

# Обработчик callback для показа текущих настроек
@dp.callback_query(lambda c: c.data == "setting_show")
async def show_current_settings(callback: CallbackQuery):
    session = SessionLocal()
    # Получаем настройки из БД (если есть таблица) или используем значения по умолчанию
    settings_text = (
        "📊 <b>Текущие настройки:</b>\n\n"
        "🔊 Volume Spike: 3.0x\n"
        "📈 IV Threshold: 10%\n"
        "📅 Expiration Days: 7\n\n"
        "<i>Эти параметры используются для генерации сигналов</i>"
    )
    session.close()
    await callback.message.answer(settings_text)
    await callback.answer()

# Обработчики для изменения настроек
@dp.callback_query(lambda c: c.data.startswith("setting_"))
async def process_setting_callback(callback: CallbackQuery, state: FSMContext):
    setting_type = callback.data.replace("setting_", "")
    
    if setting_type == "show":
        return  # Обрабатывается отдельно
    
    prompts = {
        "volume_k": "Введите множитель для всплеска объёма (например, 3.0):",
        "iv_threshold": "Введите порог роста IV в процентах (например, 10):",
        "exp_days": "Введите максимальное количество дней до экспирации (например, 7):"
    }
    
    await state.set_state(SettingsState.waiting_for_value)
    await state.update_data(setting_type=setting_type)
    await callback.message.answer(prompts.get(setting_type, "Введите новое значение:"))
    await callback.answer()

# Обработчик ввода нового значения
@dp.message(SettingsState.waiting_for_value)
async def process_new_value(message: types.Message, state: FSMContext):
    data = await state.get_data()
    setting_type = data.get("setting_type")
    
    try:
        value = float(message.text)
        
        # Валидация
        if setting_type == "volume_k" and value < 1.0:
            await message.answer("❌ Множитель должен быть >= 1.0")
            return
        if setting_type == "iv_threshold" and (value < 0 or value > 100):
            await message.answer("❌ Порог должен быть от 0 до 100")
            return
        if setting_type == "exp_days" and value < 1:
            await message.answer("❌ Количество дней должно быть >= 1")
            return
        
        # Сохранение в БД (потребуется создать таблицу Settings)
        session = SessionLocal()
        # TODO: Здесь сохранить настройку в БД
        session.close()
        
        await message.answer(f"✅ Настройка обновлена: {value}")
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Пожалуйста, введите числовое значение")
        
# Добавить новые команды после /settings
@dp.message(Command(commands=["subscribe"]))
async def cmd_subscribe(message: types.Message):
    session = SessionLocal()
    user_id = message.from_user.id
    username = message.from_user.username
    
    existing = session.query(Subscriber).filter(Subscriber.user_id == user_id).first()
    
    if existing:
        if existing.subscribed:
            await message.answer("✅ Вы уже подписаны на автоматические сигналы!")
        else:
            existing.subscribed = True
            session.commit()
            await message.answer("🔔 Подписка возобновлена! Вы будете получать сигналы автоматически.")
    else:
        new_sub = Subscriber(user_id=user_id, username=username)
        session.add(new_sub)
        session.commit()
        await message.answer(
            "🔔 Вы подписались на автоматические сигналы!\n\n"
            "Теперь вы будете получать уведомления при обнаружении необычной активности опционов.\n\n"
            "Для отписки используйте /unsubscribe"
        )
    
    session.close()

@dp.message(Command(commands=["unsubscribe"]))
async def cmd_unsubscribe(message: types.Message):
    session = SessionLocal()
    user_id = message.from_user.id
    
    subscriber = session.query(Subscriber).filter(Subscriber.user_id == user_id).first()
    
    if subscriber and subscriber.subscribed:
        subscriber.subscribed = False
        session.commit()
        await message.answer("🔕 Вы отписались от автоматических сигналов.\n\nДля возобновления используйте /subscribe")
    else:
        await message.answer("ℹ️ Вы не подписаны на автоматические сигналы.")
    
    session.close()

# === Запуск бота ===
async def start_bot():
    logger.info("🚀 Telegram bot started")
    await dp.start_polling(bot)

# === Точка входа для main.py ===
if __name__ == "__main__":
    asyncio.run(start_bot())
