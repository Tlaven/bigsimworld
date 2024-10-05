from app.core.generation.utils import RandomUtil

def generate_character(**kwargs):
    # 使用 dict.setdefault 设置默认值
    kwargs.setdefault('name', None)
    kwargs.setdefault('age', 0)
    kwargs.setdefault('wealth', 0)
    kwargs.setdefault('DOB', None)
    kwargs.setdefault('relationships', {})
    kwargs.setdefault('status', 'active')
    kwargs.setdefault('pedometer', {'step': 0, 'step_threshold': 10})
    kwargs.setdefault('relation_record', {})

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

    if kwargs.get('pedometer') is None:
        pedometers = RandomUtil.generate_pedometers(num)
    else:
        pedometers = [{'step': kwargs.get('pedometer'), 'step_threshold': 10}] * num

    return [{'name': name, 'age': age, 'gender': gender,'xing': xing,'property': 0, 'relationships': {}, 'pedometer': pedometer, 'relation_record': {}}
             for (name, gender, xing), age, pedometer in zip(names, ages, pedometers)]
