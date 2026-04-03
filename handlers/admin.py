import csv
import io
import asyncio
import os
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from config import config
from database.db import (
    get_stats,
    get_all_users_ids,
    export_users_csv,
    get_user_by_username,
    get_registration_form_mode,
    set_registration_form_mode,
)
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
        "/broadcast - Рассылка сообщения всем\n"
        "/regform - Режим регистрации (full/short)\n"
        "/find @username - Найти пользователя по юзернейму\n\n"
        "<i>💡 Отправьте мне сообщение с кастомным эмодзи (Premium), чтобы узнать его ID.</i>"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("regform"), is_admin)
async def cmd_registration_form_mode(message: types.Message):
    args = message.text.split(maxsplit=1)

    if len(args) == 1:
        current_mode = await get_registration_form_mode()
        await message.answer(
            "Текущий режим регистрации: "
            f"<b>{current_mode}</b>\n"
            "Использование: /regform full или /regform short",
            parse_mode="HTML"
        )
        return

    mode = args[1].strip().lower()
    aliases = {
        "full": "full",
        "short": "short",
        "полная": "full",
        "короткая": "short",
    }
    normalized_mode = aliases.get(mode)

    if not normalized_mode:
        await message.answer("Неверный режим. Используйте: /regform full или /regform short")
        return

    await set_registration_form_mode(normalized_mode)
    readable = "полная" if normalized_mode == "full" else "короткая"
    await message.answer(f"Режим регистрации переключен: <b>{readable}</b>", parse_mode="HTML")

@router.message(Command("find"), is_admin)
async def cmd_find_user(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Используйте формат: /find @username")
        return

    username = args[1]
    user = await get_user_by_username(username)
    
    if user:
        text = (
            f"👤 <b>Пользователь найден:</b>\n"
            f"ID: <code>{user['telegram_id']}</code>\n"
            f"Имя: {user['full_name']}\n"
            f"Username: {user['username']}\n"
            f"Email: {user['email']}\n"
            f"Регистрация: {user['registration_date']}"
        )
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(f"❌ Пользователь {username} не найден в базе данных.")

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
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Все пользователи", callback_data="broadcast_all")],
        [InlineKeyboardButton(text="📄 По файлу в проекте", callback_data="broadcast_local")]
    ])
    await message.answer("Выберите целевую аудиторию рассылки:", reply_markup=kb)
    await state.set_state(Broadcast.target_selection)

@router.callback_query(F.data == "broadcast_all", Broadcast.target_selection)
async def process_broadcast_all(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Отправьте сообщение (текст или фото с подписью) для рассылки всем пользователям.")
    await state.update_data(target_type="all")
    await state.set_state(Broadcast.message)

@router.callback_query(F.data == "broadcast_local", Broadcast.target_selection)
async def process_broadcast_local_file(callback: types.CallbackQuery, state: FSMContext):
    file_path = "data/broadcast_target.txt"
    
    if not os.path.exists(file_path):
        await callback.message.edit_text(f"❌ Файл {file_path} не найден! Создайте его и добавьте ID пользователей.")
        await state.clear()
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        user_ids = []
        for line in content.splitlines():
            line = line.strip()
            # Handle potential common delimiters
            clean_line = line.replace(',', '').replace(';', '')
            
            if clean_line.isdigit():
                user_ids.append(int(clean_line))
        
        if not user_ids:
            await callback.message.edit_text("⚠️ Файл пуст или не содержит корректных ID.")
            await state.clear()
            return

        # Unique IDs
        user_ids = list(set(user_ids))
            
        await state.update_data(target_type="list", target_users=user_ids)
        await callback.message.edit_text(f"✅ Найдено {len(user_ids)} пользователей в файле.\nТеперь отправьте сообщение для рассылки.")
        await state.set_state(Broadcast.message)
        
    except Exception as e:
        await callback.message.edit_text(f"Ошибка при чтении файла: {e}")
        await state.clear()

@router.message(Broadcast.message, is_admin)
async def process_broadcast(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target_type = data.get("target_type", "all")
    
    if target_type == "list":
        users_ids = data.get("target_users", [])
        if not users_ids:
             await message.answer("Список пользователей пуст. Рассылка отменена.")
             await state.clear()
             return
    else:
        users_ids = await get_all_users_ids()
        
    count = 0
    blocked = 0
    
    status_msg = await message.answer(f"Начинаю рассылку на {len(users_ids)} пользователей...")
    
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
