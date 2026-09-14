import json

def print_dict(dct):
    """ 缩进输出多层级字典 """
    print(json.dumps(dct, indent=4, ensure_ascii=False))