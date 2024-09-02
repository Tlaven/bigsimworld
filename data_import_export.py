import csv
import json

def import_data(file_path):
    """ 从文件导入数据。支持CSV和JSON格式。 """
    # 确定文件扩展名
    extension = file_path.split('.')[-1].lower()
    
    # 根据文件扩展名选择导入方式
    if extension == 'csv':
        with open(file_path, mode='r', newline='') as f:
            reader = csv.DictReader(f)
            data = list(reader)
    elif extension == 'json':
        with open(file_path, mode='r') as f:
            data = json.load(f)
    else:
        raise ValueError(f'Unsupported file format: {extension}')
    
    return data

def export_data(data, file_path):
    """ 将数据导出到文件。支持CSV和JSON格式。 """
    # 确定文件扩展名
    extension = file_path.split('.')[-1].lower()
    
    # 根据文件扩展名选择导出方式
    if extension == 'csv':
        if not data:
            raise ValueError('No data to export.')
        keys = data[0].keys()
        with open(file_path, mode='w', newline='') as output_file:
            dict_writer = csv.DictWriter(output_file, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(data)
    elif extension == 'json':
        with open(file_path, mode='w') as output_file:
            json.dump(data, output_file, indent=4)
    else:
        raise ValueError(f'Unsupported file format: {extension}')
