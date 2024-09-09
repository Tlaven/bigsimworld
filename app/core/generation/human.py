from app.core.generation.name import RandomUtil

def generate_character(**kwargs):
    # 使用 dict.setdefault 设置默认值
    kwargs.setdefault('name', None)
    kwargs.setdefault('age', 0)
    kwargs.setdefault('property', 0)
    kwargs.setdefault('relationships', {})

    # 如果 name 为 None，则生成名称
    if kwargs['name'] is None:
        kwargs['name'], kwargs['gender'], kwargs['xing'] = RandomUtil.generate_name(
            gender=kwargs.get('gender'), xing=kwargs.get('xing')
        )
    
    return kwargs

        
