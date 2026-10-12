from sqlalchemy.orm import sessionmaker
from functools import wraps

from app.utils.logger import setup_logger
from app.models.table import (Table, engine)

logger = setup_logger()

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
        except Exception:
            session.rollback()
            logger.exception("Error occurred during the operation")
            raise  # 重新抛出异常以便进一步处理
        finally:
            session.close()
    return wrapper

# 根据 dict 插入多个角色
@session_manager
def insert_multiple_characters_by_dict(session, characters: list[dict]):
    # 使用 bulk_insert_mappings 进行批量插入
    session.bulk_insert_mappings(Table, characters)
    logger.info(f"{len(characters)} characters inserted successfully.")

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
    except Exception:
        logger.exception(f"Error occurred during get_characters operation with filters={filters} and ids={ids}")
        raise  # 重新抛出异常
