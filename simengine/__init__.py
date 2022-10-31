from os import *


current_path = path.dirname(path.abspath(__file__))
current_directory = path.basename(current_path)

file_names_of_module = (
    file_name for file_name in listdir(current_path)
    if '.py' == file_name[-3:]
)

ignore_fiele_names = ('__init__.py', )

for file_name in (
    file_name
    for file_name in file_names_of_module
    if file_name not in ignore_fiele_names
):
    exec(f"from {current_directory}.{file_name.split('.')[0]} import *")
