import re
from datetime import datetime
from aiogram import Router, F, types, Bot
from aiogram.types import FSInputFile
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from database.db import get_user, add_user
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

# ==================== START ====================

@router.message(Command("start"), StateFilter("*"))
async def cmd_start(message: types.Message, state: FSMContext):
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
    user = await get_user(message.from_user.id)
    if user:
        await message.answer("Вы уже зарегистрированы! Скоро через бот с тобой свяжется наш менеджер менеджер и сообщит о результатах отбора 😊")
        return

    await message.answer("Супер, начнем с простого. Напиши свою Фамилию и Имя:")
    await state.set_state(Registration.full_name)

@router.message(Registration.full_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await message.answer("Сколько тебе лет? Напиши число.")
    await state.set_state(Registration.age)

@router.message(Registration.age)
async def process_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите число (возраст).")
        return
    await state.update_data(age=int(message.text))
    await message.answer("Напиши свой Email:")
    await state.set_state(Registration.email)

@router.message(Registration.email)
async def process_email(message: types.Message, state: FSMContext):
    email = message.text
    # Simple regex validation
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        await message.answer("Пожалуйста, введите корректный email.")
        return
    await state.update_data(email=email)
    
    await message.answer("Состоишь ли ты в AIESEC?", reply_markup=get_yes_no_kb())
    await state.set_state(Registration.is_aiesec_member)

@router.message(Registration.is_aiesec_member)
async def process_aiesec(message: types.Message, state: FSMContext):
    is_member = message.text.lower() == "да"
    await state.update_data(is_aiesec_member=is_member)
    
    await message.answer("Откуда узнал(а) о форуме?", reply_markup=get_source_kb())
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
        await message.answer("Откуда вы узнали о форуме?", reply_markup=types.ReplyKeyboardRemove())
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
            "Выберите ваш ВУЗ из списка или нажмите 'Другое':",
            reply_markup=get_universities_kb()
        )
        await state.set_state(Registration.uni_current_name)
    elif status == "Нет, завершил(а) обучение":
        await message.answer(
            "В каком учебном заведении ты учился(лась)? На каком направлении?\n"
            "Например: СПБГУ, Бакалавриат, Информационные системы",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.set_state(Registration.uni_past_name)
    else:
        # Skip university info
        await ask_work(message, state)

@router.message(Registration.uni_current_name)
async def process_uni_current(message: types.Message, state: FSMContext):
    uni = message.text
    if uni == "Другое":
        await message.answer("Введите название вашего ВУЗа вручную:", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(Registration.uni_current_custom)
    elif uni in config.UNIVERSITIES:
        await state.update_data(university=uni)
        await message.answer("На каком вы курсе?", reply_markup=get_course_kb())
        await state.set_state(Registration.uni_current_course)
    else:
        # Fallback
        await state.update_data(university=uni)
        await message.answer("На каком вы курсе?", reply_markup=get_course_kb())
        await state.set_state(Registration.uni_current_course)

@router.message(Registration.uni_current_custom)
async def process_uni_custom(message: types.Message, state: FSMContext):
    await state.update_data(university=message.text)
    await message.answer("На каком вы курсе?", reply_markup=get_course_kb())
    await state.set_state(Registration.uni_current_course)

@router.message(Registration.uni_current_course)
async def process_uni_course(message: types.Message, state: FSMContext):
    await state.update_data(course=message.text)
    await message.answer("Какое у вас направление обучения (специальность)?", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(Registration.uni_current_specialty)

@router.message(Registration.uni_current_specialty)
async def process_uni_specialty(message: types.Message, state: FSMContext):
    specialty = message.text
    # Save specialty separately
    await state.update_data(specialty=specialty)
    
    # We already have 'university' (from uni_name or custom) and 'course' in state
    # Rename keys if needed or just use what we have. 
    # In process_uni_current/custom we saved to 'uni_name', let's normalize this in process_expectations 
    # OR better: ensure we use consistent keys now.
    
    await ask_work(message, state)

@router.message(Registration.uni_past_name)
async def process_uni_past(message: types.Message, state: FSMContext):
    # For finished users, they input "Uni name, specialty" string.
    # We'll save it to university and leave others empty or mark as finished
    await state.update_data(university=message.text, course="Закончил", specialty="-")
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
    
    data = await state.get_data()
    
    # Prepare data for saving
    data['telegram_id'] = message.from_user.id
    username = message.from_user.username or "No Username"
    data['username'] = f"@{username}"
    data['registration_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. Save to SQLite
    await add_user(data)
    
    # 2. Append to Google Sheets
    row = [
        data['telegram_id'],
        data['username'],
        data['registration_date'],
        data['full_name'],
        data['age'],
        data['email'],
        "Yes" if data['is_aiesec_member'] else "No",
        data['source'],
        data.get('source_details', '-'),
        data['education_status'],
        data.get('university', '-'),
        data.get('course', '-'),
        data.get('specialty', '-'),
        "Yes" if data['work_status'] else "No",
        data.get('work_sphere', '-'),
        data['missing_skills'],
        data['expectations']
    ]
    # We run this in background or await if using a fast async wrapper
    # Here we made a sync service, so let's just await the wrapper (actually i made it async def but blocking code inside)
    # Wrap in try except to not fail registration if google fails
    try:
        await append_to_sheet(row)
    except Exception as e:
        pass # Logging handled inside service

    # 3. Notify Admin
    if config.ADMIN_IDS:
        admin_text = (
            f"🆕 <b>Новая регистрация!</b>\n"
            f"👤 {data['full_name']} ({data['username']})\n"
            f"📝 {data['source']}"
        )
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(admin_id, admin_text, parse_mode="HTML")
            except:
                pass

    await state.clear()
    await message.answer(
        "Регистрация завершена! Скоро через бот с тобой свяжется наш менеджер и сообщит о результатах отбора 😊",
        reply_markup=get_main_menu_kb()
    )
