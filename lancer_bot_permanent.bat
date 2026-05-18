@echo off
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "c:\Users\KHABA\OneDrive - USherbrooke\Documents\Stages\stage_hiver_2026_sénélec\Aut_rech_stage\job-bot"

:RESTART
echo [%date% %time%] Demarrage du Job Bot...
python main.py --continuous
echo [%date% %time%] Bot arrete. Redemarrage dans 30 secondes...
timeout /t 30 /nobreak
goto RESTART
