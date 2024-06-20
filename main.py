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

from modless_chat_trans.log_monitor import monitor_log_file
from modless_chat_trans.translator import Translator
from modless_chat_trans.process_message import process_message
from modless_chat_trans.display import initialization, display_message
import msvcrt

"""
Currently, it can translate messages sent by other players into various languages, significantly saving time. 
However, it does not yet support translating one's own sent messages, which is the next issue to be addressed.

Next, I will develop this program in the following areas:
- Supporting the translation of one's own sent messages before sending
- Supporting more display methods
- Supporting more translation services
- ...
"""


def callback(line):
    if processed_message := process_message(line, translator, model=model or "gpt-3.5-turbo", source_language="en-US"):
        try:
            display_message(processed_message, output_method)
        except ValueError as error:
            print(f"Error: {error}")


file_directory = input("Where is your Minecraft log folder? ")
print("What output method would you like? \n1.print\t2.graphical\t3.speech\nPlease press 1 - 3 to choose.")
while not ((output_method := {b'1': "print", b'2': "graphical", b'3': "speech"}[msvcrt.getch()]) in ["print",
                                                                                                     "graphical",
                                                                                                     "speech"]):
    print("Incorrect number")
print(f"You chose [{output_method}].")
api_url = input("Please enter the OpenAI API address (leave blank to use the official one): ")
api_key = input("Please enter your OpenAI Key: ")

translator = Translator(api_key=api_key,
                        api_url=api_url or "https://api.openai.com/v1/chat/completions")

model = input("Please enter the model name to be used for translation (leave blank to use gpt-3.5-turbo by default): ")

initialization(output_method)

monitor_log_file(file_directory, callback)
