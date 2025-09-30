# Project Documentation: Stateful Proxy Data Capture System
This document outlines the architecture, setup, and troubleshooting for a multi-component system built around a custom Mitmproxy Addon. The system captures credentials, logs specific network data, processes it, and transmits it via a non-blocking background process.

1. System Overview and Architecture
The system consists of three independent Python processes that communicate using the local file system.

Component	Technology	Primary Role	Communication
Proxy Service	mitmdump + Python Addon	Captures traffic, updates credentials, and writes raw requests/responses.	Writes: curr_req.txt, curr_res.txt (in calls/)
Parser Service	Python (margin_table_parser.py)	Reads the latest response, extracts margin data, and validates content.	Reads: curr_res.txt. Writes: Parsed data (JSON).
Data Sender/Server	Python (server.py)	Reads the parsed data and transmits it to a remote endpoint via a non-blocking thread.	Reads: Parsed JSON file. Writes: HTTP POST to remote API.

Export to Sheets
2. Setup and Deployment (Windows)
The project uses a dedicated virtual environment (.venv) for isolation and is designed for one-click execution via a batch script.

Prerequisites
Python 3.x must be installed and added to the system's PATH.

The entire project folder, including the ./.venv/ directory, must be intact.

One-Click Execution
The entire system is launched using the provided batch file.

Locate the Script: Find and double-click the run_venv.bat file in the project's root directory.

Execution: The script will first activate the virtual environment and then launch three separate Command Prompt windows concurrently for each service.

Shutdown: To stop the system, simply close all three Command Prompt windows.

Auto-Startup (Optional)
To launch the system automatically upon PC boot:

Right-click the run_venv.bat file and select Send to → Desktop (create shortcut).

Open the Windows Startup folder by pressing Win + R, typing shell:startup, and pressing Enter.

Copy the new desktop shortcut into the Startup folder.

3. Configuration
All critical variables, endpoints, and file paths are defined in the config/config.ini file.

config/config.ini Template:
Ini, TOML

[TARGETS]
; The main host used for monitoring session credentials
TARGET_HOST = eclear.mcxccl.com 
; The specific URL where the critical data is logged
MARGIN_URL = https://eclear.mcxccl.com/Bancs/RSK/RSK335.do 
; The base URL for the monitored application
MONITORED_URL = https://eclear.mcxccl.com/Bancs 

[CREDENTIALS]
; The endpoint where the final parsed data should be sent
SERVER_URL = http://localhost:5000/api/endpoint 

[PATH]
; The consistent path used by the Parser to read the raw response file
RESPONSE_FILE_PATH = calls/browser-calls/responses/cur_response.txt
4. Key Architectural Features
A. Rolling Log Management (Addon)
The Mitmproxy addon only maintains the current and previous flows for the MARGIN_URL:

Current Flow: Saved to curr_req.txt and curr_res.txt.

Previous Flow: Saved to prev_req.txt and prev_res.txt.

When a new flow arrives, the old curr_ files are instantly renamed (os.replace) to prev_ before the new files are written.

B. Robust Path Handling
To eliminate file system errors (FileNotFoundError) caused by inconsistent command prompt locations, all scripts enforce absolute path resolution:

Scripts determine their own location (os.path.abspath(__file__)).

All file access is based on the project's root directory, ensuring the writer (Addon) and readers (Parser/Sender) look at the identical location.

C. Non-Blocking Data Transmission
The data sending logic utilizes multi-threading in the server.py component. This prevents the primary process (which manages file reading and parsing) from becoming blocked or unresponsive while waiting for a response from the remote server endpoint.

5. Troubleshooting Guide
Problem	Symptom	Root Cause	Solution
FileNotFoundError	Parser/Sender fails, stating a file (e.g., cur_response.txt) is missing.	Path Inconsistency: The writer (Addon) and reader (Parser) are using slightly different paths or names.	Verify Paths: Ensure all paths in the Addon and Parser use the same absolute path logic derived from os.path.abspath(__file__) and the same exact filename (cur_response.txt).
JSONDecodeError	Error: Expecting value: line 1 column 1 (char 0) in the Sender thread.	Race Condition: The sender attempts to read the JSON file while the parser is still writing it (i.e., the file is temporarily empty).	Implement Size Check: The sender/server function must check that os.path.getsize(file) > 0 before attempting to load JSON content.
Missing Module	Batch script fails with a module not found error.	The virtual environment failed to activate correctly, or a dependency is missing.	Re-run Activation: Confirm the run_venv.bat uses the correct call command for activation and ensure all project dependencies are installed in the .venv.
