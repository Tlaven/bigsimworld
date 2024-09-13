from app.core.generation.human import generate_character, generate_characters
from app.models.crud import insert_multiple_characters



if __name__ == '__main__':
    characters = generate_characters(10000)
    insert_multiple_characters(characters)
