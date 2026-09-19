"""Seeds the database with a default admin account, a handful of sample
employees, sample food catalog items, and default settings — so the app is
immediately usable after first install. Safe to run multiple times."""

import models
from config import Config

SAMPLE_EMPLOYEES = [
    # code, name, age, sex, department, food_preference, plant
    ("EMP001", "Rahul Sharma", 29, "Male", "Production", "Veg", "1250 TPD Plant"),
    ("EMP002", "Priya Verma", 34, "Female", "Quality Control", "Non-Veg", "1250 TPD Plant"),
    ("EMP003", "Amit Singh", 41, "Male", "Maintenance", "Veg", "2000 TPD Plant"),
    ("EMP004", "Sunita Rao", 27, "Female", "HR & Admin", "Veg", "2000 TPD Plant"),
    ("EMP005", "Vikram Patel", 38, "Male", "Stores", "Non-Veg", "1250 TPD Plant"),
]

SAMPLE_FOOD_ITEMS = [
    ("Breakfast", "Veg", "Poha"),
    ("Breakfast", "Veg", "Idli Sambhar"),
    ("Breakfast", "Non-Veg", "Egg Bhurji"),
    ("Lunch", "Veg", "Veg Thali"),
    ("Lunch", "Veg", "Dal Rice"),
    ("Lunch", "Non-Veg", "Non-Veg Thali"),
    ("Lunch", "Non-Veg", "Chicken Curry Rice"),
    ("Snacks", "Snacks", "Samosa"),
    ("Snacks", "Snacks", "Bhunja"),
    ("Snacks", "Snacks", "Cutlet"),
    ("Snacks", "Snacks", "Tea/Coffee"),
    ("Dinner", "Veg", "Veg Thali"),
    ("Dinner", "Non-Veg", "Non-Veg Thali"),
]


def seed_all():
    # --- Default settings ---
    for key, value in models.DEFAULT_SETTINGS.items():
        if not models.get_setting(key, None):
            models.set_setting(key, value)

    # --- Default admin account ---
    if not models.get_user_by_username(Config.DEFAULT_ADMIN_USERNAME):
        models.create_user(username=Config.DEFAULT_ADMIN_USERNAME, password=Config.DEFAULT_ADMIN_PASSWORD, role="admin")

    # --- Sample employees + their login accounts ---
    for code, name, age, sex, dept, pref, plant in SAMPLE_EMPLOYEES:
        emp = models.get_employee_by_code(code)
        if not emp:
            emp_id = models.create_employee(employee_code=code, name=name, department=dept, age=age, sex=sex, food_preference=pref, plant=plant)
        else:
            emp_id = emp.id
        if not models.get_user_by_username(code):
            models.create_user(username=code, password=code, role="employee", employee_id=emp_id)

    # --- Sample food catalog ---
    for meal_type, food_type, item_name in SAMPLE_FOOD_ITEMS:
        models.add_or_reactivate_food_item(meal_type, food_type, item_name)
