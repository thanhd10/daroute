import os
import sys
from datetime import datetime

from definitions import ROOT_DIR

"""

- This script is used to start a script inside a screen session and save the console output
  inside a .txt file on the remote server
- Edit the variable <SCRIPT_FILE_NAME> to the absolute path to the script that should be run
- Edit the variable <SCRIPT_OUTPUT> to change the name of the .txt file, that stores the console output
"""
SCRIPT_FILE_NAME = ROOT_DIR + "/test/test_all_routes.py"
SCRIPT_OUTPUT = "console.txt"

console_log_path = ROOT_DIR + "/screen_logs/" + datetime.now().strftime('%d-%b-%Y-%H-%M-%S') + "-" + SCRIPT_OUTPUT
# start detached screen session and run command defined for -c option
screen_command = "screen -dm sh -c "
# Note: Command that is executed must be encapsulated in a string for -c option, thus the python command starts with '
# and the pipe command ends with '
python_command = "'" + sys.executable + " " + SCRIPT_FILE_NAME
pipe_txt_command = " >" + console_log_path + "; exec bash'"

command = screen_command + python_command + pipe_txt_command
print("Command that will be run inside a shell: " + command)

os.system(command)
