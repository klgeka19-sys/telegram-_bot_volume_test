import asyncio
import os
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
import edge_tts

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Память пользователей (в рабочем проекте перенесём в облачную базу)
users = {}
admin_ids = set()

# Настройки голосов: ключ -> (Название на кнопке, цена в алмазах, тип, ID голоса)
VOICES = {
    "sveta": ("👩 Светлана (RU)", 15, "edge", "ru-RU-SvetlanaNeural"),
    "dima": ("👨 Дмитрий (RU)", 15, "edge", "ru-RU-DmitryNeural"),
    "aria": ("🇺🇸 Aria (EN)", 15, "edge", "en-US-AriaNeural"),
    "vip_rachel": ("👑 VIP Эмоции (ElevenLabs)", 100, "eleven", "21m00Tcm4TlvDq8ikWAM"),
    "vip_narrator": ("👑 VIP Диктор (EN)", 100, "eleven", "7jynqzOvnVP89nA7TB0m"),
    "vip_warm_man": ("👑 VIP Тёплый мужской (EN)", 100, "eleven", "JYUzXNeyCPmymMkfcicu"),
}

# Пакеты алмазов: ключ -> (Название, кол-во алмазов, цена в Звёздах)
PACKAGES = {
    "pack_test": ("🧪 Тест: 10 💎", 10, 1),
    "pack_150": ("💎 150 алмазов", 150, 50),
    "pack_750": ("💎 750 алмазов", 750, 250),
    "pack_2000": ("💎 2000 алмазов", 2000, 500),
}

def get_user(user_id):
    if user_id not in users:
        users[user_id] = {"diamonds": 30, "voice": "sveta"}
    return users[user_id]

def main_menu(user_id):
    u = get_user(user_id)
    v_name, v_price, _, _ = VOICES[u["voice"]]
    kb = InlineKeyboardBuilder()
    kb.button(text="🎙 Выбрать голос", callback_data="menu_voices")
    kb.button(text="💎 Пополнить баланс", callback_data="menu_shop")
    kb.adjust(1)
    bal_text = "♾ Безлимит (Админ)" if user_id in admin_ids else f"**{u['diamonds']} алмазов**"
    return (
        f"✨ **ИИ Озвучка текста**\n\n"
        f"💎 Твой баланс: {bal_text}\n"
        f"🎙 Выбранный голос: **{v_name}** ({v_price} 💎 за текст)\n\n"
        f"Просто отправь мне любой текст сообщением, и я сразу его озвучу!",
        kb.as_markup()
    )

@dp.message(CommandStart())
async def cmd_start(message: Message):
    text, markup = main_menu(message.from_user.id)
    await message.answer(text, reply_markup=markup, parse_mode="Markdown")

# СЕКРЕТНЫЕ КОМАНДЫ ДЛЯ ТЕБЯ (АДМИНА)
@dp.message(F.text == "/vip")
async def activate_vip_admin(message: Message):
    user_id = message.from_user.id
    admin_ids.add(user_id)
    u = get_user(user_id)
    u["diamonds"] += 10000
    await message.answer(
        f"👑 **Режим владельца активирован!**\n\n"
        f"• Твой числовой ID: `{user_id}`\n"
        f"• Начислено **+10 000 💎**, алмазы больше не списываются при тестах!",
        parse_mode="Markdown"
    )

@dp.message(F.text == "/myid")
async def show_my_id(message: Message):
    await message.answer(f"🆔 Твой числовой Telegram ID: `{message.from_user.id}`", parse_mode="Markdown")

@dp.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    text, markup = main_menu(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    await callback.answer()

# МЕНЮ ВЫБОРА ГОЛОСА
@dp.callback_query(F.data == "menu_voices")
async def show_voices(callback: CallbackQuery):
    u = get_user(callback.from_user.id)
    kb = InlineKeyboardBuilder()
    for key, (name, price, _, _) in VOICES.items():
        mark = "✅ " if u["voice"] == key else ""
        kb.button(text=f"{mark}{name} — {price} 💎", callback_data=f"set_voice:{key}")
    kb.button(text="🔙 Назад", callback_data="back_main")
    kb.adjust(1)
    await callback.message.edit_text(
        "🎙 **Выбери голос для озвучки:**\n\n"
        "• Обычные голоса — до 500 символов.\n"
        "• VIP голоса — живые эмоции (до 150 символов).",
        reply_markup=kb.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("set_voice:"))
async def select_voice(callback: CallbackQuery):
    voice_key = callback.data.split(":")[1]
    u = get_user(callback.from_user.id)
    u["voice"] = voice_key
    text, markup = main_menu(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    await callback.answer("Голос выбран!")

# МЕНЮ ПОКУПКИ АЛМАЗОВ
@dp.callback_query(F.data == "menu_shop")
async def show_shop(callback: CallbackQuery):
    kb = InlineKeyboardBuilder()
    for key, (title, diamonds, stars) in PACKAGES.items():
        kb.button(text=f"{title} — Оплатить {stars} ⭐", callback_data=f"buy:{key}")
    kb.button(text="🔙 Назад", callback_data="back_main")
    kb.adjust(1)
    await callback.message.edit_text(
        "💎 **Пополнение баланса алмазов**\n\n"
        "Выбери подходящий пакет. Оплата проходит мгновенно через Telegram Stars ⭐:",
        reply_markup=kb.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

# ВЫСТАВЛЕНИЕ СЧЁТА В TELEGRAM STARS
@dp.callback_query(F.data.startswith("buy:"))
async def send_stars_invoice(callback: CallbackQuery):
    pack_key = callback.data.split(":")[1]
    title, diamonds, stars = PACKAGES[pack_key]
    
    await callback.message.answer_invoice(
        title=title,
        description=f"Пополнение баланса на {diamonds} алмазов для озвучки текста",
        payload=f"diamonds:{diamonds}",
        provider_token="",  # Обязательно пустая строка для Telegram Stars!
        currency="XTR",
        prices=[LabeledPrice(label=f"{diamonds} алмазов", amount=stars)]
    )
    await callback.answer()

@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def on_payment_success(message: Message):
    payload = message.successful_payment.invoice_payload
    diamonds_added = int(payload.split(":")[1])
    u = get_user(message.from_user.id)
    u["diamonds"] += diamonds_added
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🎙 Перейти к озвучке", callback_data="back_main")
    await message.answer(
        f"✅ **Оплата прошла успешно!**\n\n"
        f"Начислено: **+{diamonds_added} 💎**\n"
        f"Текущий баланс: **{u['diamonds']} 💎**",
        reply_markup=kb.as_markup(),
        parse_mode="Markdown"
    )

# ГЕНЕРАЦИЯ ГОЛОСА ПО ТЕКСТУ
@dp.message(F.text)
async def generate_voice(message: Message):
    user_id = message.from_user.id
    u = get_user(user_id)
    v_name, price, v_type, v_id = VOICES[u["voice"]]
    text = message.text.strip()
    is_admin = user_id in admin_ids

    if not is_admin and u["diamonds"] < price:
        kb = InlineKeyboardBuilder()
        kb.button(text="💎 Купить алмазы", callback_data="menu_shop")
        await message.answer(
            f"❌ Недостаточно алмазов!\nДля этого голоса нужно **{price} 💎**, а у тебя **{u['diamonds']} 💎**.",
            reply_markup=kb.as_markup(),
            parse_mode="Markdown"
        )
        return

    if v_type == "eleven" and len(text) > 150:
        await message.answer("⚠️ Для **VIP-голоса** максимум **150 символов** за один раз. Сократи текст и отправь снова!", parse_mode="Markdown")
        return

    if v_type == "edge" and len(text) > 500:
        await message.answer("⚠️ Максимальная длина текста — **500 символов** за раз.", parse_mode="Markdown")
        return

    wait_msg = await message.answer("🎙 Озвучиваю текст, подожди пару секунд...")

    try:
        if v_type == "edge":
            tts = edge_tts.Communicate(text, voice=v_id)
            audio_bytes = bytearray()
            async for chunk in tts.stream():
                if chunk["type"] == "audio":
                    audio_bytes.extend(chunk["data"])
            audio_data = bytes(audio_bytes)
        else:
            if not ELEVENLABS_API_KEY:
                await wait_msg.edit_text("⚙️ VIP-голос пока настраивается администратором. Выбери обычный голос в меню!")
                return
            url = f"https://elevenlabs.io{v_id}"
            headers = {
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json"
            }
            payload = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status != 200:
                        await wait_msg.edit_text("❌ Ошибка сервиса VIP-озвучки. Попробуй позже или выбери обычный голос.")
                        return
                    audio_data = await resp.read()

        if not is_admin:
            u["diamonds"] -= price
            caption_bal = f"💎 Осталось: {u['diamonds']} алмазов"
        else:
            caption_bal = "👑 Режим админа (безлимит)"

        voice_file = BufferedInputFile(audio_data, filename="voice.ogg")
        await message.answer_voice(
            voice=voice_file,
            caption=f"🎙 {v_name}\n{caption_bal}"
        )
        await wait_msg.delete()

    except Exception:
        await wait_msg.edit_text("❌ Произошла ошибка при озвучке. Попробуй отправить текст ещё раз.")

# ПИНОК ДЛЯ RENDER (приёмник + автопинг)
async def handle_ping(request):
    return web.Response(text="Bot is alive!")

async def keep_alive():
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url:
        return
    while True:
        await asyncio.sleep(600)  # Стучимся каждые 10 минут
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    pass
        except Exception:
            pass

async def main():
    app = web.Application()

app.router.add_get("/", handle_ping)
runner = web.AppRunner(app)
await runner.setup()
await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000))).start()
asyncio.create_task(keep_alive())  # Запускаем фоновый пинок
await dp.start_polling(bot)
if name == "main":
asyncio.run(main())
