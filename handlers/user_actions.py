import logging
from pathlib import Path
from aiogram import Router, F, types, Bot
from aiogram.types import FSInputFile
from aiogram.fsm.context import FSMContext
from database.db import get_user, set_ambassador_candidate
from keyboards.builders import (
    get_ambassador_kb, 
    get_cancel_kb, 
    get_main_menu_kb,
    get_info_submenu_kb,
    get_socials_kb
)
from handlers.states import Question
from config import config

router = Router()
logger = logging.getLogger(__name__)

PROGRAM_FILE_ID_CACHE_PATH = Path("data/program_photo_file_id.txt")
_program_photo_file_id_cache = None


def _read_program_photo_file_id() -> str | None:
    global _program_photo_file_id_cache
    if _program_photo_file_id_cache:
        return _program_photo_file_id_cache

    try:
        if PROGRAM_FILE_ID_CACHE_PATH.exists():
            file_id = PROGRAM_FILE_ID_CACHE_PATH.read_text(encoding="utf-8").strip()
            if file_id:
                _program_photo_file_id_cache = file_id
                return file_id
    except Exception as e:
        logger.warning(f"Failed to read cached program photo file_id: {e}")

    return None


def _save_program_photo_file_id(file_id: str) -> None:
    global _program_photo_file_id_cache
    _program_photo_file_id_cache = file_id
    try:
        PROGRAM_FILE_ID_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        PROGRAM_FILE_ID_CACHE_PATH.write_text(file_id, encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to persist cached program photo file_id: {e}")

# ℹ️ Информация о форуме
@router.message(F.text == "ℹ️ Информация о форуме")
async def show_info_menu(message: types.Message):
    logger.info(f"User {message.from_user.id} requested Info menu")
    # Check if both are confirmed
    # Show summary AND the submenu so users can see details/photos
    if config.IS_DATE_CONFIRMED and config.IS_PLACE_CONFIRMED:
        text = (
            "<b>Форум SkillUp</b>\n\n"
            "🗓 <b>Дата:</b> 26 апреля\n"
            "⌚ <b>Время:</b> с 11:00 до 19:00\n"
            "📍 <b>Место:</b> ITHUB"
        )
        await message.answer(text, reply_markup=get_info_submenu_kb(), parse_mode="HTML")
    else:
        # Show sub-menu
        text = (
            "Форум SkillUp — это площадка для взаимодействия студентов, выпускников ВУЗов и начинающих специалистов с представителями успешных компаний и опытными профессионалами в различных областях.\n\n"
            "<b>Что тебя ждёт на SkillUp?</b>\n"
            "◼️ 2 образовательных трека;\n"
            "◼️ Возможность получить актуальную информацию от экспертов и практиков;\n"
            "◼️ Нетворкинг и возможность найти единомышленников в своём городе;\n"
            "◼️ Конкурсы и подарки.\n\n"
            "Форум создаётся экспертом в области развития лидерства молодёжи — международной некоммерческой организацией AIESEC.\n\n"
            "Участие на форуме бесплатное! Регистрируйся и присоединяйся к команде единомышленников!\n\n"
            "Выбери, что тебя интересует:"
        )
        await message.answer(text, reply_markup=get_info_submenu_kb(), parse_mode="HTML")

@router.callback_query(F.data == "info_date")
async def info_date(callback: types.CallbackQuery):
    if config.IS_DATE_CONFIRMED:
        text = "🗓 Форум пройдет 26 апреля!!!"
    else:
        text = "🗓 Форум состоится в конце апреля. Скоро сообщим точную дату и время 🙂"
    await callback.message.answer(text)
    await callback.answer()

@router.callback_query(F.data == "info_place")
async def info_place(callback: types.CallbackQuery):
    if config.IS_PLACE_CONFIRMED:
         text = (
            "<b>Наша площадка — IThub college!</b> 🚀\n\n"
            "У колледжа есть огромное пространство в сердце Петербурга, идеально подходящее для нашего форума (кстати, для него мы займём целых два этажа!)\n\n"
            
            "📍<b>Адрес:</b> ITHUB (СпБ, Аптекарский проспект 2, Ⓜ️Петроградская)"
         )
         try:
            photo = FSInputFile("resources/venue.jpg")
            await callback.message.answer_photo(photo, caption=text, parse_mode="HTML")
         except Exception:
            await callback.message.answer(text, parse_mode="HTML")
    else:
         text = "📍 Место проведения в процессе подтверждения. Как только всё будет готово, мы напишем!"
         await callback.message.answer(text)
    
    await callback.answer()


# 📅 Программа форума
@router.message(F.text == "📅 Программа форума")
async def show_program(message: types.Message):
    logger.info(f"User {message.from_user.id} requested Program")
    cached_file_id = _read_program_photo_file_id()

    if cached_file_id:
        try:
            await message.answer_photo(cached_file_id)
            return
        except Exception as e:
            logger.warning(f"Failed to send program photo by cached file_id: {e}")

    try:
        photo = FSInputFile("resources/program.jpg")
        sent = await message.answer_photo(photo)
        if sent.photo:
            _save_program_photo_file_id(sent.photo[-1].file_id)
    except Exception as e:
        logger.error(f"Failed to send program photo: {e}")
        await message.answer("Не удалось загрузить программу форума. Попробуй позже.")

# 🗣 Спикеры
@router.message(F.text == "🗣 Спикеры")
async def show_speakers(message: types.Message):
    logger.info(f"User {message.from_user.id} requested Speakers")
    # Заглушка
    text = (
        "Мы пригласили экспертов из топовых компаний!\n"
        "Список спикеров формируется и скоро появится здесь."
    )
    await message.answer(text)

# 📞 Контакты
@router.message(F.text == "📞 Контакты")
async def show_contacts(message: types.Message):
    logger.info(f"User {message.from_user.id} requested Contacts")
    text = (
        "По всем вопросам пиши сюда: @qleafye\n\n"
        "Наши группы:\n"
        "VK: https://vk.com/skillup_aiesec\n"
        "TG: https://t.me/skillup_aiesec"
    )
    await message.answer(text, reply_markup=get_socials_kb())

# ⭐ Стать Амбассадором
@router.message(F.text == "⭐ Стать Амбассадором")
async def become_ambassador_menu(message: types.Message):
    logger.info(f"User {message.from_user.id} requested Ambassador menu")
    text = (
        "<b>Стать Амбассадором SkillUp</b>\n\n"
        "Ты можешь стать связующим звеном между участниками и организаторами – тем, кто помогает форуму расти и становиться лучше!\n\n"
        "<b>Выполняя несложные задания, ты:</b>\n"
        "• Прокачаешь коммуникацию, лидерство и организаторские скиллы\n"
        "• Найдёшь единомышленников внутри нашего комьюнити\n"
        "• Получишь эксклюзивный мерч и подарки от организаторов\n"
        "• Добавишь сертификат амбассадора в своё портфолио"
    )
    await message.answer(text, reply_markup=get_ambassador_kb(), parse_mode="HTML")

@router.callback_query(F.data == "become_ambassador")
async def process_become_ambassador(callback: types.CallbackQuery, bot: Bot):
    user_info = f"@{callback.from_user.username}" if callback.from_user.username else f"ID: {callback.from_user.id}"
    logger.info(f"User {callback.from_user.id} applied to be Ambassador")
    link = f"tg://user?id={callback.from_user.id}"
    
    # Notify Admin
    if config.ADMIN_IDS:
         for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id, 
                    f"🌟 <b>Заявка в амбассадоры!</b>\nПользователь: <a href='{link}'>{user_info}</a>",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id} about ambassador application: {e}")
                pass

    # Update DB
    await set_ambassador_candidate(callback.from_user.id)
    
    await callback.message.edit_text(
        "Спасибо, что хочешь стать частью команды SkillUp!\nМы рассмотрим твою заявку и вскоре с тобой свяжется наш менеджер для уточнения деталей", 
        reply_markup=None
    )
    await callback.answer()

# ❓ Задать вопрос
@router.message(F.text == "❓ Задать вопрос")
async def ask_organizer_start(message: types.Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} wants to ask a question")
    await message.answer(
        "Напиши свой вопрос, и мы передадим его организаторам.",
        reply_markup=get_cancel_kb()
    )
    await state.set_state(Question.waiting_for_question)

@router.message(Question.waiting_for_question)
async def process_question(message: types.Message, state: FSMContext, bot: Bot):
    if message.text == "Отмена":
        logger.info(f"User {message.from_user.id} canceled question")
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=get_main_menu_kb())
        return

    question_text = message.text
    logger.info(f"User {message.from_user.id} sent question: {question_text}")
    user_info = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.from_user.id}"
    
    admin_text = f"❓ <b>Новый вопрос от {user_info}:</b>\n\n{question_text}"
    
    # Send to all admins
    sent_count = 0
    if config.ADMIN_IDS:
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(admin_id, admin_text, parse_mode="HTML")
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send question to admin {admin_id}: {e}")
                pass
        
        if sent_count > 0:
            await message.answer("Твой вопрос отправлен!", reply_markup=get_main_menu_kb())
        else:
            logger.error(f"Failed to send question from {message.from_user.id} to any admin")
            await message.answer("Не удалось отправить вопрос, попробуйте позже.", reply_markup=get_main_menu_kb())
    else:
        logger.warning("No admins configured to receive questions")
        await message.answer("Администраторы не настроены.", reply_markup=get_main_menu_kb())
    
    await state.clear()
