from aiogram.fsm.state import StatesGroup, State

class Registration(StatesGroup):
    full_name = State()
    age = State()
    email = State() # Added back email
    
    # AIESEC Membership
    is_aiesec_member = State()
    
    # Source Logic
    source = State()
    source_details_ambassador = State()
    source_details_friend = State()
    source_details_partner = State()
    source_details_other = State()
    
    # Education Logic
    education_status = State()
    
    # Current Student Branch
    uni_current_name = State()
    uni_current_custom = State()
    uni_current_course = State()
    uni_current_specialty = State()
    
    # Past/Finished Branch
    uni_past_choose = State()
    uni_past_custom = State()
    uni_past_specialty = State()
    
    # Work Logic
    work_status = State()
    work_sphere_current = State() # If working
    work_career_plan = State()    # If not working
    
    # Skills & Expectations
    missing_skills = State()
    expectations = State()

class Question(StatesGroup):
    waiting_for_question = State()

class Broadcast(StatesGroup):
    message = State()
