# Creating a Python Virtual Environment on Windows and macOS

## 1. Check if Python Is Installed

Open **Command Prompt / PowerShell** (Windows) or **Terminal** (macOS):

```bash
python --version
or
python3 --version

If a Python version is displayed, Python is installed.
Install Python if Needed
Download from: https://www.python.org/downloads/
Windows: Check Add Python to PATH during installation
macOS: Use the official installer or Homebrew (brew install python)

2. Navigate to Your Project Directory
cd path/to/your/project
Example:
cd Desktop/my_project

3. Create a Virtual Environment

Windows
python -m venv venv

macOS
python3 -m venv venv

This creates a folder named venv containing the virtual environment.

4. Activate the Virtual Environment

Windows (Command Prompt)
venv\Scripts\activate

Windows (PowerShell)
venv\Scripts\Activate.ps1

If activation is blocked in PowerShell:
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

macOS / Linux
source venv/bin/activate

5. Verify Activation
The terminal prompt will show:
(venv)
Check the Python version:
python --version

6. Install Packages Inside the Environment
pip install requests
Save dependencies:
pip freeze > requirements.txt

7. Deactivate the Virtual Environment
deactivate


------------------

pip install langchain-anthropic
pip install langchain-google-genai

python basic.py   