from os import *


current_path = path.dirname(path.abspath(__file__))
current_directory = path.basename(current_path)

file_names_of_module = [
    file_name for file_name in listdir(current_path)
    if '.py' == file_name[-3:]
]

ignore_fiele_names = ('__init__.py', '__pycache__')

for ignore_fiele_name in ignore_fiele_names:
    if ignore_fiele_name in file_names_of_module:
        file_names_of_module.remove(ignore_fiele_name)

for file_name in file_names_of_module:
    exec(f"from {current_directory}.{file_name.split('.')[0]} import *")
