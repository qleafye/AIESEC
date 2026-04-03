import re
import logging
from datetime import datetime
from aiogram import Router, F, types, Bot
from aiogram.types import FSInputFile
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from database.db import get_user, add_user, get_registration_form_mode
from handlers.states import Registration
from services.sheets import append_to_sheet
from keyboards.builders import (
    get_main_menu_kb,
    get_yes_no_kb,
    get_source_kb,
    get_education_status_kb,
    get_universities_kb,
    get_course_kb
)
from config import config

router = Router()
logger = logging.getLogger(__name__)

# ==================== START ====================

@router.message(Command("start"), StateFilter("*"))
async def cmd_start(message: types.Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} requested /start")
    await state.clear()
    text = (
        "Привет, будущий IT-специалист!\n"
        "Это бот карьерного форума SkillUp – твоего старта карьеры в мире IT.\n\n"
        "SkillUp – форум про IT для молодых специалистов, студентов, которые только начинают свой карьерный путь!\n\n"
        "<b>Что тебя ждёт на SkillUp?</b>\n"
        "◼️ 2 образовательных трека;\n"
        "◼️ Возможность получить актуальную информацию от экспертов и практиков;\n"
        "◼️ Нетворкинг и возможность найти единомышленников в своём городе;\n"
        "◼️ Конкурсы и подарки.\n\n"
        "<b>В этом боте ты сможешь:</b>\n"
        "🔹 Зарегистрироваться на форум\n"
        "🔹 Узнать всё о программе, спикерах и возможностях\n"
        "🔹 Получить ответы на вопросы о форуме\n\n"
        "Готов сделать шаг к карьере мечты? Давай начнем с регистрации!"
    )
    try:
        photo = FSInputFile("resources/start.jpg")
        await message.answer_photo(photo, caption=text, reply_markup=get_main_menu_kb(), parse_mode="HTML")
    except Exception:
        # Fallback if image not found or error
        await message.answer(text, reply_markup=get_main_menu_kb(), parse_mode="HTML")

# ==================== REGISTRATION FLOW ====================

@router.message(F.text == "📝 Зарегистрироваться")
async def start_registration(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    logger.info(f"User {user_id} started registration")
    user = await get_user(message.from_user.id)
    registration_mode = await get_registration_form_mode()
    
    # Check if user exists. Admins can re-register infinitely.
    if user:
        if user_id in config.ADMIN_IDS:
            await message.answer("🛠 Ты являешься администратором, поэтому можешь зарегистрироваться повторно.")
        else:
            logger.info(f"User {user_id} tried to register again but is already registered")
            await message.answer("Ты уже зарегистрирован!😊")
            return

    if registration_mode == "short":
        await message.answer("Супер, короткая форма включена. Напиши свою Фамилию и Имя:")
    else:
        await message.answer("Супер, начнем с простого. Напиши свою Фамилию и Имя:")
    await state.set_state(Registration.full_name)

@router.message(Registration.full_name)
async def process_name(message: types.Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} provided name: {message.text}")
    await state.update_data(full_name=message.text)
    await message.answer("Сколько тебе лет? Напиши число.")
    await state.set_state(Registration.age)

@router.message(Registration.age)
async def process_age(message: types.Message, state: FSMContext, bot: Bot):
    if not message.text.isdigit():
        logger.warning(f"User {message.from_user.id} provided invalid age: {message.text}")
        await message.answer("Пожалуйста, введи число (возраст).")
        return
    logger.info(f"User {message.from_user.id} provided age: {message.text}")
    await state.update_data(age=int(message.text))

    registration_mode = await get_registration_form_mode()
    if registration_mode == "short":
        await finalize_registration(message, state, bot=bot, is_short=True)
        return

    await message.answer("Напиши свой Email:")
    await state.set_state(Registration.email)

@router.message(Registration.email)
async def process_email(message: types.Message, state: FSMContext):
    email = message.text
    # Simple regex validation
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        logger.warning(f"User {message.from_user.id} provided invalid email: {email}")
        await message.answer("Пожалуйста, введи корректный email.")
        return
    
    logger.info(f"User {message.from_user.id} provided email: {email}")
    await state.update_data(email=email)
    
    await message.answer("Состоишь ли ты в AIESEC?", reply_markup=get_yes_no_kb())
    await state.set_state(Registration.is_aiesec_member)

@router.message(Registration.is_aiesec_member)
async def process_aiesec(message: types.Message, state: FSMContext):
    is_member = message.text.lower() == "да"
    await state.update_data(is_aiesec_member=is_member)
    
    await message.answer("Откуда ты узнал(а) о форуме?", reply_markup=get_source_kb())
    await state.set_state(Registration.source)

@router.message(Registration.source)
async def process_source(message: types.Message, state: FSMContext):
    source = message.text
    if source not in ["От амбассадора", "От друга", "В ВК", "В ТГ", "В соцсетях партнера форума", "Увидел плакат в вузе", "Другое"]:
         # Fallback if user types manually something strange, or just accept it. 
         # Let's simple accept it to avoid stuck.
         pass
         
    await state.update_data(source=source)
    
    # Branching based on source
    if source == "От амбассадора":
        await message.answer("Напиши фамилию и имя амбассадора:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(Registration.source_details_ambassador)
    elif source == "От друга":
        await message.answer("Напиши фамилию и имя друга:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(Registration.source_details_friend)
    elif source == "В соцсетях партнера форума":
        await message.answer("От какого партнера?", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(Registration.source_details_partner)
    elif source == "Другое":
        await message.answer("Откуда ты узнал(а) о форуме?", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(Registration.source_details_other)
    else:
        # Skip details, move to Education
        await ask_education(message, state)

# --- Source Details Branches ---
@router.message(Registration.source_details_ambassador)
async def process_source_ambassador(message: types.Message, state: FSMContext):
    await state.update_data(source_details=f"Ambassador: {message.text}")
    await ask_education(message, state)

@router.message(Registration.source_details_friend)
async def process_source_friend(message: types.Message, state: FSMContext):
    await state.update_data(source_details=f"Friend: {message.text}")
    await ask_education(message, state)

@router.message(Registration.source_details_partner)
async def process_source_partner(message: types.Message, state: FSMContext):
    await state.update_data(source_details=f"Partner: {message.text}")
    await ask_education(message, state)

@router.message(Registration.source_details_other)
async def process_source_other(message: types.Message, state: FSMContext):
    # For 'other', we overwrite the 'source' with what they wrote, or keep 'Source: Other, Details: ...'
    # Let's keep source='Другое' and source_details='Text' for consistency
    await state.update_data(source_details=message.text)
    await ask_education(message, state)

# --- Education LogicHelper ---
async def ask_education(message: types.Message, state: FSMContext):
    await message.answer("Учишься ли ты сейчас?", reply_markup=get_education_status_kb())
    await state.set_state(Registration.education_status)

@router.message(Registration.education_status)
async def process_ed_status(message: types.Message, state: FSMContext):
    status = message.text
    await state.update_data(education_status=status)
    
    if status == "Да, в ВУЗе или колледже":
        await message.answer(
            "Выбери свой ВУЗ из списка или нажми 'Другое':",
            reply_markup=get_universities_kb()
        )
        await state.set_state(Registration.uni_current_name)
    elif status == "Нет, завершил(а) обучение":
        await message.answer(
            "В каком учебном заведении ты учился(лась)?",
            reply_markup=get_universities_kb()
        )
        await state.set_state(Registration.uni_past_choose)
    else:
        # Skip university info
        await ask_work(message, state)

@router.message(Registration.uni_current_name)
async def process_uni_current(message: types.Message, state: FSMContext):
    uni = message.text
    if uni == "Другое":
        await message.answer("Введи название своего ВУЗа вручную:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(Registration.uni_current_custom)
    elif uni in config.UNIVERSITIES:
        await state.update_data(university=uni)
        await message.answer("На каком ты курсе?", reply_markup=get_course_kb())
        await state.set_state(Registration.uni_current_course)
    else:
        # Fallback
        await state.update_data(university=uni)
        await message.answer("На каком ты курсе?", reply_markup=get_course_kb())
        await state.set_state(Registration.uni_current_course)

@router.message(Registration.uni_current_custom)
async def process_uni_custom(message: types.Message, state: FSMContext):
    await state.update_data(university=message.text)
    await message.answer("На каком ты курсе?", reply_markup=get_course_kb())
    await state.set_state(Registration.uni_current_course)

@router.message(Registration.uni_current_course)
async def process_uni_course(message: types.Message, state: FSMContext):
    await state.update_data(course=message.text)
    await message.answer("Какое у тебя направление обучения (специальность)?", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(Registration.uni_current_specialty)

@router.message(Registration.uni_current_specialty)
async def process_uni_specialty(message: types.Message, state: FSMContext):
    specialty = message.text
    # Save specialty separately
    await state.update_data(specialty=specialty)
    await ask_work(message, state)

@router.message(Registration.uni_past_choose)
async def process_uni_past_choose(message: types.Message, state: FSMContext):
    uni = message.text
    if uni == "Другое":
        await message.answer("Введи название своего ВУЗа вручную:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(Registration.uni_past_custom)
    else:
        await state.update_data(university=uni, course="Закончил")
        await message.answer("Какое у тебя было направление обучения (специальность)?", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(Registration.uni_past_specialty)

@router.message(Registration.uni_past_custom)
async def process_uni_past_custom(message: types.Message, state: FSMContext):
    await state.update_data(university=message.text, course="Закончил")
    await message.answer("Какое у тебя было направление обучения (специальность)?", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(Registration.uni_past_specialty)

@router.message(Registration.uni_past_specialty)
async def process_uni_past_specialty(message: types.Message, state: FSMContext):
    await state.update_data(specialty=message.text)
    await ask_work(message, state)

# --- Work LogicHelper ---
async def ask_work(message: types.Message, state: FSMContext):
    await message.answer("Работаешь сейчас?", reply_markup=get_yes_no_kb())
    await state.set_state(Registration.work_status)

@router.message(Registration.work_status)
async def process_work_status(message: types.Message, state: FSMContext):
    is_working = message.text.lower() == "да"
    await state.update_data(work_status=is_working)
    
    if is_working:
        await message.answer("В какой сфере работаешь?", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(Registration.work_sphere_current)
    else:
        await message.answer("В какой сфере хочешь строить карьеру?", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(Registration.work_career_plan)

@router.message(Registration.work_sphere_current)
async def process_work_sphere(message: types.Message, state: FSMContext):
    await state.update_data(work_sphere=message.text)
    await ask_skills(message, state)

@router.message(Registration.work_career_plan)
async def process_career_plan(message: types.Message, state: FSMContext):
    await state.update_data(work_sphere=message.text)
    await ask_skills(message, state)

# --- Skills & Final ---
async def ask_skills(message: types.Message, state: FSMContext):
    await message.answer("Как считаешь, каких софт и хард скиллов тебе не хватает на данный момент?")
    await state.set_state(Registration.missing_skills)

@router.message(Registration.missing_skills)
async def process_skills(message: types.Message, state: FSMContext):
    await state.update_data(missing_skills=message.text)
    await message.answer(
        "Отлично, последний вопрос. Какие у тебя ожидания от форума? "
        "Что хочешь узнать? Каких активностей ждешь?"
    )
    await state.set_state(Registration.expectations)

@router.message(Registration.expectations)
async def process_expectations(message: types.Message, state: FSMContext, bot: Bot):
    await state.update_data(expectations=message.text)
    await finalize_registration(message, state, bot=bot, is_short=False)


def build_sheet_row(data: dict) -> list:
    # Keep a stable number and order of columns to avoid Google Sheets conflicts.
    return [
        data.get('telegram_id'),
        data.get('username', '-'),
        data.get('registration_date', '-'),
        data.get('full_name', '-'),
        data.get('age', '-'),
        data.get('email', '-'),
        "Yes" if data.get('is_aiesec_member') else "No",
        data.get('source', '-'),
        data.get('source_details', '-'),
        data.get('education_status', '-'),
        data.get('university', '-'),
        data.get('course', '-'),
        data.get('specialty', '-'),
        "Yes" if data.get('work_status') else "No",
        data.get('work_sphere', '-'),
        data.get('missing_skills', '-'),
        data.get('expectations', '-'),
    ]


async def finalize_registration(message: types.Message, state: FSMContext, bot: Bot | None, is_short: bool):
    data = await state.get_data()
    logger.info(f"User {message.from_user.id} finished registration. Saving data.")

    data['telegram_id'] = message.from_user.id
    username = message.from_user.username or "No Username"
    data['username'] = f"@{username}"
    data['registration_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if is_short:
        data.setdefault('email', '-')
        data.setdefault('is_aiesec_member', False)
        data.setdefault('source', 'Короткая форма')
        data.setdefault('source_details', '-')
        data.setdefault('education_status', '-')
        data.setdefault('university', '-')
        data.setdefault('course', '-')
        data.setdefault('specialty', '-')
        data.setdefault('work_status', False)
        data.setdefault('work_sphere', '-')
        data.setdefault('missing_skills', '-')
        data.setdefault('expectations', '-')

    await add_user(data)
    logger.info(f"User {message.from_user.id} saved to DB.")

    row = build_sheet_row(data)
    try:
        await append_to_sheet(row)
        logger.info(f"User {message.from_user.id} saved to Google Spreadsheet.")
    except Exception as e:
        logger.error(f"Error saving user {message.from_user.id} to Google Sheets: {e}")

    if bot and config.ADMIN_IDS:
        source_text = data.get('source', 'Короткая форма')
        admin_text = (
            f"🆕 <b>Новая регистрация!</b>\n"
            f"👤 {data.get('full_name', '-')} ({data.get('username', '-')})\n"
            f"📝 {source_text}"
        )
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(admin_id, admin_text, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")

    await state.clear()
    await message.answer(
        "Регистрация завершена! Увидимся на форуме! 🎉\n\n",
        reply_markup=get_main_menu_kb()
    )

    try:
        cv_guide = "BQACAgIAAxkDAAIQO2nAQvQ9dovIDxH8Excq2nLzGrwAA_6bAAJoRwABSlP2ExucbIGmOgQ"
        await message.answer_document(cv_guide, caption="🎁 А вот и твой бонус за регистрацию — гайд по составлению резюме!")
    except Exception as e:
        logger.error(f"Failed to send CV guide to {message.from_user.id}: {e}")
