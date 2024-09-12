from app.core.generation.utils import RandomUtil

def generate_character(**kwargs):
    # 使用 dict.setdefault 设置默认值
    kwargs.setdefault('name', None)
    kwargs.setdefault('age', 0)
    kwargs.setdefault('property', 0)
    kwargs.setdefault('relationships', {})
    kwargs.setdefault('status', 'active')

    # 如果 name 为 None，则生成名称
    if kwargs['name'] is None:
        kwargs['name'], kwargs['gender'], kwargs['xing'] = RandomUtil.generate_name(
            gender=kwargs.get('gender'), xing=kwargs.get('xing')
        )
    
    return kwargs

def generate_characters(num, **kwargs):
    names = RandomUtil.genrate_names(num)
    num = len(names)
    if kwargs.get('age') is None:
        ages = RandomUtil.generate_ages(num)
    else:
        ages = [kwargs.get('age')] * num
    return [{'name': name, 'age': age, 'gender': gender,'xing': xing,'property': 0, 'relationships': {}} for (name, gender, xing), age in zip(names, ages)]
