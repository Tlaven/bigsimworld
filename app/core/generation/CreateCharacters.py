import sys
from pathlib import Path

# 获取主程序的绝对路径
current_script_path = Path(__file__).resolve().parent.parent.parent.parent
# 将app目录添加到sys.path
sys.path.append(str(current_script_path))

# 现在可以正常导入app内的模块
from app.core.generation.human import generate_character, generate_characters
from app.models.crud import insert_multiple_characters_by_dict

if __name__ == '__main__':
    characters = generate_characters(10000)
    insert_multiple_characters_by_dict(characters)
