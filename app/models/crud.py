import logging
from sqlalchemy.orm import sessionmaker
from functools import wraps
from app.models.table import (Table, engine)


# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 创建一个 handler，用于写入日志文件
file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.INFO)

# 创建一个 formatter，设置日志的格式
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# 添加 handler 到 logger
logger.addHandler(file_handler)

# 手动管理 Session 的创建
def get_session():
    Session = sessionmaker(bind=engine)
    return Session()

# 通用的 session 管理装饰器
def session_manager(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        session = get_session()
        try:
            result = func(session, *args, **kwargs)
            session.commit()
            return result
        except Exception as e:
            session.rollback()
            logger.exception("Error occurred during the operation")
            raise  # 重新抛出异常以便进一步处理
        finally:
            session.close()
    return wrapper

# # 插入单个角色
# @session_manager
# def insert_character(session, **kwargs) -> int:
#     new_character = Table(**kwargs)
#     session.add(new_character)
#     session.flush()  # 刷新数据库连接，确保数据被写入
#     new_character_id = new_character.id
#     logger.info(f"Character {new_character_id} inserted successfully.")
#     return new_character_id

# 根据 object 插入多个角色
@session_manager
def insert_multiple_characters(session, characters: dict[int: object]):
    # 构建批量更新的字典列表
    updates = [
        {key: value for key,
          value in character.__dict__.items() if key in Table.__table__.columns.keys()}
            for character in characters.values()
    ]
    # 使用 bulk_insert_mappings 进行批量插入
    session.bulk_insert_mappings(Table, updates)
    logger.info(f"{len(characters)} characters inserted successfully.")

# 根据 dict 插入多个角色
@session_manager
def insert_multiple_characters_by_dict(session, characters: list[dict]):
    # 使用 bulk_insert_mappings 进行批量插入
    session.bulk_insert_mappings(Table, characters)
    logger.info(f"{len(characters)} characters inserted successfully.")

# # 更新单个角色
# @session_manager
# def update_character(session, character_id, new_data):
#     character = session.query(Table).filter_by(id=character_id).first()
#     if character:
#         for key, value in new_data.items():
#             setattr(character, key, value)
#         logger.info(f"Character with ID {character_id} updated successfully.")
#     else:
#         logger.warning(f"Character with ID {character_id} not found.")

@session_manager
def update_multiple_characters(session, characters: dict[int: object]):
    # 构建批量更新的字典列表
    updates = [
        {key: value for key,
          value in character.__dict__.items() if key in Table.__table__.columns.keys()}
            for character in characters.values()
    ]
    # 使用 bulk_update_mappings 进行批量更新
    session.bulk_update_mappings(Table, updates)
    logger.info(f"{len(updates)} characters updated successfully.")

# 根据 dict 更新多个角色
@session_manager
def update_multiple_characters_by_dict(session, characters: list[dict]):
    # 使用 bulk_update_mappings 进行批量更新
    session.bulk_update_mappings(Table, characters)
    logger.info(f"{len(characters)} characters updated successfully.")

# # 删除符合条件的角色
# @session_manager
# def delete_characters_by_conditions(session, **kwargs):
#     delete_query = session.query(Table).filter_by(**kwargs)
#     deleted_count = delete_query.delete(synchronize_session=False)
#     logger.info(f"{deleted_count} characters deleted successfully.")

def get_characters(session, filters=None, ids=None) -> list[tuple]:
    try:
        query = session.query(Table).with_entities(*Table.__table__.columns)
        
        # 根据传入的 ids 和 filters 逐步构建查询
        if ids:
            query = query.filter(Table.id.in_(ids))
            logger.info(f"Querying characters with ids: {ids}")
        if filters:
            query = query.filter_by(**filters)
            logger.info(f"Querying characters with filters: {filters}")
        
        characters = session.execute(query).fetchall()
        return characters  # 将返回放到 try 块内，防止异常时执行
    except Exception as e:
        logger.exception(f"Error occurred during get_characters operation with filters={filters} and ids={ids}")
        raise  # 重新抛出异常


# # 基于 status 和 end_time 的组合索引进行查询
# def get_characters_by_status_and_end_time(session, status, end_time):
#     try:
#         characters = session.query(Table).filter(
#             Table.status == status,
#             Table.end_time == end_time
#         ).all()
#     except Exception as e:
#             logger.exception("Error occurred during the operation")
#             raise  # 重新抛出异常以便进一步处理
#     return characters

# # 查看所有记录
# def get_all_characters(session):
#     characters = session.query(Table).all()
    
#     if characters:
#         result = [{col.name: getattr(character, col.name) for col in Table.__mapper__.c} for character in characters]
#         for item in result:
#             logger.info(f"Found character: {item}")
#         return result
#     else:
#         logger.info("No characters found in the database.")
#         return []
