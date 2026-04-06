import logging
import html
from datetime import datetime

from aiogram import Bot, F, Router, types
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile

from config import config
from database.db import add_user, get_user
from handlers.states import Registration
from keyboards.builders import get_main_menu_kb
from services.sheets import append_to_sheet

router = Router()
logger = logging.getLogger(__name__)
CV_GUIDE_FILE_ID = "BQACAgIAAxkDAAIQO2nAQvQ9dovIDxH8Excq2nLzGrwAA_6bAAJoRwABSlP2ExucbIGmOgQ"

START_TEXT = (
    "Привет, будущий IT-специалист!\n"
    "Это бот карьерного форума SkillUp – твоего старта карьеры в мире IT.\n\n"
    "SkillUp – форум про IT для молодых специалистов и студентов, которые только начинают свой карьерный путь.\n\n"
    "<b>Что тебя ждёт на SkillUp?</b>\n"
    "◼️ 2 образовательных трека;\n"
    "◼️ Возможность получить актуальную информацию от экспертов и практиков;\n"
    "◼️ Нетворкинг и возможность найти единомышленников в своём городе;\n"
    "◼️ Конкурсы и подарки.\n\n"
    "Готов сделать шаг к карьере мечты? Давай начнем с регистрации!"
)


def _extract_referrer_id(command_args: str | None, current_user_id: int) -> int | None:
    if not command_args:
        return None

    arg = command_args.strip()
    if not arg.isdigit():
        return None

    referrer_id = int(arg)
    if referrer_id == current_user_id:
        return None

    return referrer_id


def _build_sheet_row(data: dict) -> list:
    """Keep compatibility with the existing 17-column sheet."""
    details_parts = []
    if data.get("referrer_id"):
        details_parts.append(f"Referrer ID: {data['referrer_id']}")
    details = " | ".join(details_parts) if details_parts else "-"

    return [
        data.get("telegram_id"),
        data.get("username", "-"),
        data.get("registration_date", "-"),
        data.get("full_name", "-"),
        data.get("age", "-"),
        "-",
        "No",
        "Реферальная ссылка" if data.get("referrer_id") else "Самостоятельно",
        details,
        "-",
        "-",
        "-",
        "-",
        "No",
        "-",
        "-",
        "-",
    ]


async def _start_registration_flow(message: types.Message, state: FSMContext, referrer_id: int | None = None):
    await state.clear()
    if referrer_id:
        await state.update_data(referrer_id=referrer_id)

    await message.answer(
        "Отлично, начинаем регистрацию." if not referrer_id else "Отлично, ты пришёл по приглашению друга. Начинаем регистрацию."
    )
    await message.answer("Напиши свою Фамилию и Имя:")
    await state.set_state(Registration.full_name)


@router.message(Command("start"), StateFilter("*"))
async def cmd_start(message: types.Message, state: FSMContext, command: CommandObject | None = None):
    user_id = message.from_user.id
    logger.info(f"User {user_id} requested /start")

    user = await get_user(user_id)
    referrer_id = _extract_referrer_id(command.args if command else None, user_id)

    if user:
        try:
            photo = FSInputFile("resources/start.jpg")
            await message.answer_photo(photo, caption=START_TEXT, reply_markup=get_main_menu_kb(), parse_mode="HTML")
        except Exception:
            await message.answer(START_TEXT, reply_markup=get_main_menu_kb(), parse_mode="HTML")
        return

    await _start_registration_flow(message, state, referrer_id=referrer_id)


@router.message(F.text == "📝 Зарегистрироваться")
async def start_registration(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user = await get_user(user_id)

    if user and user_id not in config.ADMIN_IDS:
        await message.answer("Ты уже зарегистрирован!", reply_markup=get_main_menu_kb())
        return

    await _start_registration_flow(message, state)


@router.message(Registration.full_name)
async def process_full_name(message: types.Message, state: FSMContext):
    full_name = (message.text or "").strip()
    if len(full_name.split()) < 2:
        await message.answer("Пожалуйста, укажи и имя, и фамилию.")
        return

    await state.update_data(full_name=full_name)
    await message.answer("Теперь напиши свой возраст числом:")
    await state.set_state(Registration.age)


@router.message(Registration.age)
async def process_age(message: types.Message, state: FSMContext, bot: Bot):
    raw_age = (message.text or "").strip()
    if not raw_age.isdigit():
        await message.answer("Возраст должен быть числом. Попробуй еще раз.")
        return

    age = int(raw_age)
    if age < 10 or age > 120:
        await message.answer("Укажи корректный возраст числом от 10 до 120.")
        return

    await state.update_data(age=age)
    await finalize_registration(message, state, bot)


async def finalize_registration(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    data["telegram_id"] = message.from_user.id
    data["username"] = f"@{message.from_user.username}" if message.from_user.username else "-"
    data["registration_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    data.setdefault("email", "-")
    data.setdefault("is_aiesec_member", False)
    data.setdefault("source", "Реферальная ссылка" if data.get("referrer_id") else "Самостоятельно")
    data.setdefault("source_details", f"Referrer ID: {data.get('referrer_id', '-')}")
    data.setdefault("education_status", "-")
    data.setdefault("university", "-")
    data.setdefault("course", "-")
    data.setdefault("specialty", "-")
    data.setdefault("work_status", False)
    data.setdefault("work_sphere", "-")
    data.setdefault("missing_skills", "-")
    data.setdefault("expectations", "-")

    await add_user(data)

    try:
        await append_to_sheet(_build_sheet_row(data))
    except Exception as e:
        logger.error(f"Failed to append user {message.from_user.id} to Google Sheet: {e}")

    if config.ADMIN_IDS:
        safe_name = html.escape(str(data.get("full_name", "-")))
        safe_username = html.escape(str(data.get("username", "-")))
        safe_source = html.escape(str(data.get("source", "-")))
        admin_text = (
            f"🆕 <b>Новая регистрация!</b>\n"
            f"👤 {safe_name} ({safe_username})\n"
            f"🎂 {data.get('age', '-')}\n"
            f"📝 {safe_source}"
        )
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(admin_id, admin_text, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")

    await state.clear()
    await message.answer("Регистрация завершена! Увидимся на форуме! 🎉", reply_markup=get_main_menu_kb())

    try:
        await message.answer_document(
            CV_GUIDE_FILE_ID,
            caption="🎁 А вот и твой бонус за регистрацию — гайд по составлению резюме!",
        )
    except Exception as e:
        logger.error(f"Failed to send CV guide to {message.from_user.id}: {e}")
