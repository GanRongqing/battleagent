import os
import json
import simulation.database as database

DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def update_database(engine, scenario_data):
    """
        根据想定数据配置内容更新当前引擎仿真数据库数据
    :param engine: 仿真引擎
    :param scenario_data: 想定数据
    :return: None
    """
    # 取得属性映射关系配置数据
    properties_config = get_properties_config()

    # 取得所有配置的型号数据
    models = scenario_data["baseData"]["models"]
    models = database.naive(models)

    for category, model_dict in models.items():
        for model, model_data in model_dict.items():
            # 如果有当前型号数据，则更新
            if model in engine.db:
                pass
            # 如果没有当前型号数据，则添加
            else:
                # 如果是地面设施
                if category == "facility":
                    pass
                # 如果是其他平台
                elif category == "otherPlatform":
                    pass
                # 如果是武器系统
                elif category == "weaponsystem":
                    pass
                # 如果是挂架
                elif category == "mount":
                    pass
                # 如果是其它分类
                else:
                    pass

# 更新船
def update_ship_data(engine, model_dict, config_dict):



    for model, model_data in model_dict.items():



        if model not in engine.db:
            engine.db[model] = {}

        for k, v in config_dict.items():
            engine.db[model][k] = model_data[v]


# 更新facility
def update_facility_data(engine, model_dict, config_dict):
    """
        更新地面设施数据
    :param engine:
    :param model_dict:
    :return:
    """
    class_dict = {
        "Airport":"Airport",
        "Base":"Base",
        "FixedFacility":"FixedFacility"
  }
    for model, model_data in model_dict.items():
        if model not in engine.db:
            engine.db[model] = {}

        class_name = model_data['class_name']
        for k, v in config_dict[class_dict[class_name]].items():
            if isinstance(v,dict):
                for k1,v1 in v.items():
                    engine.db[model][k1] = v1
            else:
                engine.db[model][k] = model_data[v]

        # # 如果有当前型号数据，则更新
        # if model in engine.db:
        #     pass
        # # 如果没有当前型号数据，则添加
        # else:
        #     pass


def get_properties_config():
    """
        取得属性映射关系配置数据
    :return: 属性映射关系配置数据
    """
    properties_config_file_path = "sim_script/20240510想定编辑仿真/properties_config.json"
    with open(os.path.join(DIR, properties_config_file_path), encoding="UTF-8") as f:
        properties_config = json.load(f)
    return properties_config

