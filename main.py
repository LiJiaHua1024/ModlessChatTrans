# Copyright (C) 2024 LiJiaHua1024
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import sys

from modless_chat_trans.display import initialization, display_message
from modless_chat_trans.log_monitor import monitor_log_file
from modless_chat_trans.process_message import process_message
from modless_chat_trans.translator import Translator

"""
Currently, it can translate messages sent by other players into various languages, significantly saving time. 
However, it does not yet support translating one's own sent messages, which is the next issue to be addressed.

Next, I will develop this program in the following areas:
- Supporting the translation of one's own sent messages before sending
- Supporting more display methods
- Supporting more translation services
- ...
"""

if sys.platform.startswith("win"):
    import msvcrt

    getch = msvcrt.getch
elif sys.platform.startswith("linux"):
    import tty
    import termios


    def getch():
        file_descriptor = sys.stdin.fileno()
        old_terminal_settings = termios.tcgetattr(file_descriptor)
        try:
            tty.setraw(file_descriptor)
            key_pressed = sys.stdin.read(1)
        finally:
            termios.tcsetattr(file_descriptor, termios.TCSADRAIN, old_terminal_settings)
        return key_pressed.encode()
else:
    print("Sorry, so far we don't support the operating system you are using.")
    input("Press Enter to exit.")
    sys.exit(0)


def callback(line):
    if processed_message := process_message(line, translator, model=model or "gpt-3.5-turbo",
                                            source_language=source_language, target_language=target_language):
        try:
            display_message(processed_message, output_method)
        except ValueError as error:
            print(f"Error: {error}")


file_directory = input("Where is your Minecraft log folder? ")
print("What output method would you like?\n1.print\n2.graphical\n3.speech\n4.httpserver\nPlease press 1 - 4 to choose.")
OUTPUT_METHOD_MAPPING = {
    b'1': "print",
    b'2': "graphical",
    b'3': "speech",
    b'4': "httpserver"
}
while not ((output_method := OUTPUT_METHOD_MAPPING[getch()]) in OUTPUT_METHOD_MAPPING.values()):
    print("Incorrect number")

print(f"You chose [{output_method}].")

http_port = 0

if output_method == "httpserver":
    while True:
        if http_port := input("Please enter the HTTP server port number (leave blank to use 5000): "):
            try:
                if 1 <= (http_port := int(http_port)) <= 65535:
                    break
                else:
                    print("Port number must be between 1 and 65535. Please enter a valid port number.")
            except ValueError:
                print("Invalid input. Please enter a valid port number.")
        else:
            http_port = 5000
            break

source_language = input("Please enter the language of the text you want to translate: ")
target_language = input("Please enter the language for the translation: ")
api_url = input("Please enter the OpenAI API address (leave blank to use the official one): ")
api_key = input("Please enter your OpenAI Key: ")

translator = Translator(api_key=api_key,
                        api_url=api_url or "https://api.openai.com/v1/chat/completions")

model = input("Please enter the model name to be used for translation (leave blank to use gpt-3.5-turbo by default): ")

initialization(output_method, http_port=http_port)

monitor_log_file(file_directory, callback)
