import datetime as dt
import json
import os
import uuid
import xml.etree.ElementTree as et
from copy import deepcopy

import grpc
from flask import Flask, request, send_from_directory
from openpyxl.reader.excel import load_workbook

from simulation import simserver_pb2, simserver_pb2_grpc


_HOST = '192.168.240.41'
_PORT = '6000'
channel = grpc.insecure_channel("{0}:{1}".format(_HOST, _PORT))
client = simserver_pb2_grpc.GreeterStub(channel=channel)
user_name = "liuwenqing"

BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_PATH = os.path.join(BASE_PATH, "sim_script", "20241113平行博弈仿真", "scenario_files")
EXCEL_FILE_NAME = "easyExcelTest.xlsx"
DATETIME_FMT = "%Y%m%d%H%M%S%f"
DATETIME_FMT_SPLIT = "%Y-%m-%d %H:%M:%S"

EQUIP_DICT = {
    'SES_Mun_SeaTOSeaMissle_B6': ("32@6201", "1603", "SM6-SEA"),
    'SES_Platform_USV_BlueTikangCruiser': ("1@8700", "1602", "Ticonderoga"),
    'SES_Platform_USV_Destroyer_AliBurke': ("1@8600", "1366", "Burke"),
    'SES_Platform_Submarine_UFightPlatform': ("32@10000", "1604", "CrossMediaPlatform"),
    'SES_Platform_USV_BlueNimiziji': ("32@8200", "1601", "Nimitz"),
    'SES_Platform_KFixedStation_Lead': ("34@2", "1628", "Base")
}

app = Flask(__name__)


def gen_uuid():
    return str(uuid.uuid4()).replace("-", "")


def get_time_str():
    return dt.datetime.now().strftime(DATETIME_FMT)


def get_sheet_data_by_name(wb, sheet_name):
    """
        根据sheet页名称获取sheet页数据
    :param wb: excel工作簿
    :param sheet_name: sheet页名称
    :return: sheet页数据
    """
    sheet = wb.get_sheet_by_name(sheet_name)
    
    
    
    row_list = []
    
    for row_index, row in enumerate(sheet.iter_rows()):
        if row_index == 0:
            continue
        row_list.append([cell.value for cell in row])
    return row_list


def gen_sce_info_element(wb, sce_id):
    sheet_data_list = get_sheet_data_by_name(wb, "想定基本信息")
    sce_name, start_time, end_time, sim_step, sce_topic = sheet_data_list[0][1:]
    sce_info_element = et.Element('Info', {"Desc": "想定基本信息"})
    et.SubElement(sce_info_element, "Attribute", {"Val": sce_id, "Type": "string", "Name": "uid"})
    et.SubElement(sce_info_element, "Attribute", {"Val": sce_name, "Type": "string", "Name": "name"})
    et.SubElement(sce_info_element, "Attribute", {"Val": "1.0", "Type": "string", "Name": "version"})
    et.SubElement(sce_info_element, "Attribute", {"Val": "admin", "Name": "author"})
    et.SubElement(sce_info_element, "Attribute", {"Val": sce_topic, "Type": "string", "Name": "desc"})
    cur_time = dt.datetime.now().strftime(DATETIME_FMT_SPLIT)
    et.SubElement(sce_info_element, "Attribute", {"Val": cur_time, "Type": "string", "Name": "createTime"})
    et.SubElement(sce_info_element, "Attribute", {"Val": start_time, "Type": "string", "Name": "startTime"})
    et.SubElement(sce_info_element, "Attribute", {"Val": end_time, "Type": "string", "Name": "endTime"})
    et.SubElement(sce_info_element, "Attribute", {"Val": str(sim_step), "Type": "simPeriod", "Name": "仿真步长"})
    return sce_info_element


def gen_force_entity_element(force):
    
    name, longitude, latitude, model = force[:4]
    side, entity_id = force[6], force[9]
    entity_element = et.Element('Entity',
                                {"IdInSce": str(entity_id), "CommanderId": "-1", "CarrierId": "-1",
                                 "EquipId": EQUIP_DICT[model][1], "Name": name, "MName": name, "ModelNum": "1"})
    base_info_element = et.SubElement(entity_element, "BaseInfo")
    et.SubElement(base_info_element, "Attribute", {"Val": side, "Type": "string", "Name": "attach"})
    et.SubElement(base_info_element, "Attribute", {"Val": '-1', "Type": "string", "Name": "carrierID"})
    et.SubElement(base_info_element, "Attribute", {"Val": EQUIP_DICT[model][0], "Type": "string", "Name": "icon"})
    et.SubElement(base_info_element, "Attribute", {"Val": str(longitude), "Type": "double", "Name": "实体位置（纬度）"})
    et.SubElement(base_info_element, "Attribute", {"Val": str(latitude), "Type": "double", "Name": "实体位置（经度）"})
    et.SubElement(base_info_element, "Attribute", {"Val": name, "Type": "string", "Name": "实体名称"})
    et.SubElement(base_info_element, "Attribute", {"Val": model, "Type": "string", "Name": "type"})
    return entity_element


def gen_weapon_entity_element(weapon, force, index):
    
    entity_name, weapon_name, model, weapon_num, weapon_id = weapon
    
    longitude, latitude, side, force_id = force[1], force[2], force[6], force[9]
    
    m_weapon_name = f"{entity_name}_{EQUIP_DICT[model][2]}[{index + 1}]"
    entity_element = et.Element('Entity',
                                {"IdInSce": str(weapon_id), "CommanderId": "-1", "CarrierId": str(force_id),
                                 "EquipId": EQUIP_DICT[model][1], "Name": weapon_name, "MName": m_weapon_name,
                                 "ModelNum": str(weapon_num)})
    base_info_element = et.SubElement(entity_element, "BaseInfo")
    et.SubElement(base_info_element, "Attribute", {"Val": side, "Type": "string", "Name": "attach"})
    et.SubElement(base_info_element, "Attribute", {"Val": str(force_id), "Type": "string", "Name": "carrierID"})
    et.SubElement(base_info_element, "Attribute", {"Val": EQUIP_DICT[model][0], "Type": "string", "Name": "icon"})
    et.SubElement(base_info_element, "Attribute", {"Val": str(longitude), "Type": "double", "Name": "实体位置（纬度）"})
    et.SubElement(base_info_element, "Attribute", {"Val": str(latitude), "Type": "double", "Name": "实体位置（经度）"})
    et.SubElement(base_info_element, "Attribute", {"Val": weapon_name, "Type": "string", "Name": "实体名称"})
    et.SubElement(base_info_element, "Attribute", {"Val": model, "Type": "string", "Name": "type"})
    return entity_element


def gen_carry_member_element(weapon, force):
    
    model, weapon_num, weapon_id = weapon[2:]
    
    force_id = force[9]
    carry_element = et.Element('carryMember')
    et.SubElement(carry_element, "Attribute", {"Val": str(uuid.uuid4()), "Name": "UID"})
    et.SubElement(carry_element, "Attribute", {"Val": str(force_id), "Name": "carrierID"})
    et.SubElement(carry_element, "Attribute", {"Val": str(weapon_id), "Name": "passengerEleID"})
    et.SubElement(carry_element, "Attribute", {"Val": EQUIP_DICT[model][1], "Name": "modelId"})
    et.SubElement(carry_element, "Attribute", {"Val": str(weapon_num), "Name": "weaponNum"})
    et.SubElement(carry_element, "Attribute", {"Val": EQUIP_DICT[model][0], "Name": "weaponIcon"})
    return carry_element


def gen_att_element(wb):
    
    red_element = et.Element('ATT', {"Attach": "红方", "Id": "704", "Text": "红方", "Name": "Red",
                                     "color": "rgba(250, 14, 14, 1)"})
    
    blue_element = et.Element('ATT', {"Attach": "蓝方", "Id": "703", "Text": "蓝方", "Name": "Blue",
                                      "color": "rgba(14, 72, 249, 1)"})
    
    carry_element = et.Element("carryInfo")

    
    force_list = get_sheet_data_by_name(wb, "兵力部署")
    
    force_dict = {}
    
    entity_id = 2026
    
    for force in force_list:
        
        force.append(entity_id)
        entity_id += 1
        
        force_dict[force[0]] = force
        
        entity_element = gen_force_entity_element(force)
        if force[6] == "红方":
            red_element.append(entity_element)
        else:
            blue_element.append(entity_element)

    
    weapon_list = get_sheet_data_by_name(wb, "搭载武器")

    
    weapon_name_dict = {}
    
    for weapon in weapon_list:
        
        entity_name, weapon_name, weapon_type, weapon_num = weapon
        
        force = force_dict[entity_name]

        for index in range(int(weapon_num)):
            
            weapon_copy = deepcopy(weapon)
            
            weapon_copy.append(entity_id)
            entity_id += 1

            
            if weapon_name not in weapon_name_dict:
                weapon_name_dict[weapon_name] = 1
            else:
                
                weapon_copy[1] = f"{weapon_name}-{weapon_name_dict[weapon_name]}"
                weapon_name_dict[weapon_name] += 1

            
            entity_element = gen_weapon_entity_element(weapon_copy, force, index)
            if force[6] == "红方":
                red_element.append(entity_element)
            else:
                blue_element.append(entity_element)

            
            carry_element.append(gen_carry_member_element(weapon_copy, force))

    return red_element, blue_element, carry_element


def excel_to_xml(sce_id):
    
    wb = load_workbook(f'{UPLOAD_PATH}/{sce_id}/easyExcelTest.xlsx')
    
    root = et.Element('Scenario', attrib={"Id": "2024", "Version": "2.0"})
    
    root.append(gen_sce_info_element(wb, sce_id))
    
    red_element, blue_element, carry_element = gen_att_element(wb)
    root.append(red_element)
    root.append(blue_element)
    root.append(carry_element)

    tree = et.ElementTree(element=root, file=None)
    
    xml_path = f'{UPLOAD_PATH}/{sce_id}'
    xml_name = f'ScenarioFile.xml'
    
    tree.write(f'{xml_path}/{xml_name}', encoding='UTF-8')
    return xml_path, xml_name


def get_entity_ids_from_xml(sce_id):
    tree = et.parse(f'{UPLOAD_PATH}/{sce_id}/ScenarioFile.xml')
    scenario_data = tree.getroot()
    entity_ids = {}
    
    entity_elements = scenario_data.findall('ATT/Entity')
    for entity_element in entity_elements:
        
        entity_id = entity_element.get('IdInSce')
        entity_name = entity_element.get('Name')
        m_entity_name = entity_element.get('MName')
        entity_ids[m_entity_name] = (int(entity_id), entity_name)

    return entity_ids


@app.route('/admin/scenario/upload', methods=["POST"])
def upload():
    
    excel_file = request.files.get("multipartFile")
    
    
    
    sce_id = gen_uuid()
    file_path = f"{UPLOAD_PATH}/{sce_id}"
    if not os.path.exists(file_path):
        os.makedirs(file_path)
    
    excel_file.save(os.path.join(file_path, EXCEL_FILE_NAME))

    
    return {"code": 1000, "msg": "请求成功", "data": sce_id}


@app.route('/admin/scenario/download/<string:sce_id>', methods=["GET"])
def download(sce_id: str):
    
    xml_path, xml_name = excel_to_xml(sce_id)
    
    return send_from_directory(xml_path, xml_name)


@app.route('/cmd/load', methods=["POST"])
def load():
    
    data = request.get_data()
    str_data = data.decode('utf-8')
    data_dict = json.loads(str_data)

    
    sce_seq, sce_id = data_dict["sceSeq"], data_dict["sceId"]
    
    rounds, multi_speed = data_dict["rounds"], data_dict["multiSpeed"]

    
    res_data = []
    for index in range(rounds):
        res_data.append({
            "sceId": sce_id,  
            "beginRoundNum": index + 1,  
            "endRoundNum": index + 1,  
            "udsGlobalId": gen_uuid(),  
            "multiSpeed": multi_speed  
        })

    return {
        "code": 1000,
        "msg": "请求成功",
        "data": res_data
    }

@app.route('/cmd/start', methods=["POST"])
def start():
    data = request.get_data()
    str_data = data.decode('utf-8')
    param_list = json.loads(str_data)

    if not param_list:
        return {
            "code": 1000,
            "msg": "请求成功",
            "data": []
        }

    
    res_data = []
    
    engine_ids = []
    
    sce_id, ratio = param_list[0]["sceId"], param_list[0]["multiSpeed"]
    for param in param_list:
        engine_id = param["udsGlobalId"]
        res_data.append({
            "code": 1,
            "codeMsg": "Successful.",
            "udsGlobalId": engine_id
        })
        engine_ids.append(engine_id)

    entity_ids = get_entity_ids_from_xml(sce_id)

    data = {
        "flag": "base_server",
        "func_name": "start_parallel_sim",
        "ip": "127.0.0.1",
        "source": "test",
        "user_name": user_name,
        'kwargs': {
            'script_name': '平行博弈大样本仿真',
            'exp_method': '全遍历',
            'kwargs': {
                'engine_names': engine_ids,
                "nats_ip": f"{_HOST}:4222",
                "sce_id": sce_id,
                "ratio": ratio,
                "entity_ids": entity_ids
            },
            'param_data': {
                'engine_index': list(range(len(engine_ids)))
            },
            'single_group_exp_num': 1
        }
    }

    msg = json.dumps(data)
    res = client.control(simserver_pb2.MsgStr(msg=msg))
    print(res)

    return {
        "code": 1000,
        "msg": "请求成功",
        "data": res_data
    }


if __name__ == '__main__':
    app.run(host=_HOST, port=8091)
