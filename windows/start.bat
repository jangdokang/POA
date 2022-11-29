FOR %%A IN (%~dp0\.) DO SET folder=%%~dpA
call %folder%\.venv\Scripts\activate.bat
call python %folder%\run.py
pause