FOR %%A IN (%~dp0\.) DO SET folder=%%~dpA
call python -m venv %folder%\.venv
call %folder%\.venv\Scripts\activate.bat
call %folder%\.venv\Scripts\python.exe -m pip install --upgrade pip
call pip install -r %folder%\requirements.txt
pause