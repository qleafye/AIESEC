import csv
import io
import asyncio
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile
from config import config
from database.db import get_stats, get_all_users_ids, export_users_csv
from handlers.states import Broadcast

router = Router()

def is_admin(message: types.Message):
    return message.from_user.id in config.ADMIN_IDS

@router.message(Command("admin"), is_admin)
async def cmd_admin_help(message: types.Message):
    text = (
        "👮‍♂️ <b>Панель администратора</b>\n\n"
        "/stats - Статистика регистраций\n"
        "/export - Скачать базу пользователей (CSV)\n"
        "/broadcast - Рассылка сообщения всем\n\n"
        "<i>💡 Отправьте мне сообщение с кастомным эмодзи (Premium), чтобы узнать его ID.</i>"
    )
    await message.answer(text, parse_mode="HTML")

def has_custom_emoji(message: types.Message):
    if not message.entities:
        return False
    return any(e.type == "custom_emoji" for e in message.entities)

@router.message(has_custom_emoji, is_admin)
async def get_entity_id(message: types.Message):
    # Check for custom emoji
    text_response = ""
    for entity in message.entities:
        if entity.type == "custom_emoji":
            text_response += f"Emoji: {entity.custom_emoji_id}\nCode: &lt;tg-emoji emoji-id=\"{entity.custom_emoji_id}\"&gt;�&lt;/tg-emoji&gt;\n\n"
    
    if text_response:
        await message.answer(f"🆔 ID кастомных эмодзи:\n{text_response}", parse_mode="HTML")

@router.message(Command("stats"), is_admin)
async def cmd_stats(message: types.Message):
    total, ambassadors, top_unis = await get_stats()
    
    text = (
        f"📊 <b>Статистика:</b>\n"
        f"Всего регистраций: {total}\n"
        f"Из них амбассадоров: {ambassadors}\n\n"
        f"🏆 <b>Топ-3 ВУЗа:</b>\n"
    )
    
    for i, (uni, count) in enumerate(top_unis, 1):
        text += f"{i}. {uni} — {count}\n"
        
    await message.answer(text, parse_mode="HTML")

@router.message(Command("export"), is_admin)
async def cmd_export(message: types.Message):
    headers, rows = await export_users_csv()
    
    output = io.StringIO()
    # Используем разделитель ;, так как Excel в РФ часто его ждет
    # quotechar='"' нужен чтобы экранировать поля с кавычками или разделителями
    writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    writer.writerows(rows)
    
    output.seek(0)
    # Используем utf-8-sig, чтобы добавить BOM (Byte Order Mark). 
    # Это подскажет Excel, что файл в кодировке UTF-8 и починит кракозябры.
    file_bytes = output.getvalue().encode('utf-8-sig')
    document = BufferedInputFile(file_bytes, filename="users.csv")
    
    await message.answer_document(document, caption="База данных пользователей")

@router.message(Command("broadcast"), is_admin)
async def cmd_broadcast(message: types.Message, state: FSMContext):
    await message.answer("Отправьте сообщение (текст или фото с подписью) для рассылки всем пользователям.")
    await state.set_state(Broadcast.message)

@router.message(Broadcast.message, is_admin)
async def process_broadcast(message: types.Message, state: FSMContext, bot: Bot):
    users_ids = await get_all_users_ids()
    count = 0
    blocked = 0
    
    await message.answer(f"Начинаю рассылку на {len(users_ids)} пользователей...")
    
    for chat_id in users_ids:
        try:
            await message.send_copy(chat_id)
            count += 1
            await asyncio.sleep(0.05) # Prevent flood wait
        except Exception:
            blocked += 1
            
    await message.answer(
        f"Рассылка завершена.\n"
        f"✅ Успешно: {count}\n"
        f"❌ Недоступно: {blocked}"
    )
    await state.clear()
