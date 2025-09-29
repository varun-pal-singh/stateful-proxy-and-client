@echo off
echo Activating Virtual Environment...

:: Use 'call' to execute the activate script and return control to the batch file.
call ".\.venv\Scripts\activate.bat"

if errorlevel 1 (
    echo ERROR: Could not activate virtual environment. Exiting.
    pause
    goto :eof
)

echo Virtual environment activated successfully.

:: --- 1. Start Mitmproxy (using mitmdump) ---
:: We use 'start' to open this in its own window.
start "Mitmproxy Service" cmd /k mitmdump -p 8080 -s .\mcx_stateful_proxy.py

:: --- 2. Start Response Parser ---
start "Response Parser" cmd /k python .\parser\margin_table_parser.py

:: --- 3. Start Data Sender ---
start "Data Sender" cmd /k python .\client\margin_data_sender.py

echo.
echo All components are started in separate windows.
echo You can now close this current window.
exit