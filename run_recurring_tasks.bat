@echo off
cd /d C:\Users\kilga\rk-ops
call .venv\Scripts\activate.bat
python manage.py generate_recurring_tasks >> recurring_tasks.log 2>&1