@echo off
cd /d C:\Users\kilga\rk-ops
call .venv\Scripts\activate.bat
python manage.py process_operations >> operations_scheduler.log 2>&1