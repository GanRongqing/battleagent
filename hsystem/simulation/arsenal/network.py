import collections
import numpy as np
import pdb
import copy
import time
import random
import json
from datetime import datetime
from dateutil import tz
import asyncio

from .. import algorithm as alg
from .. import core


class StarNetwork(core.arch.Network):
    """ 星型通信网络
    """
    def __init__(self, engine, model):
        super().__init__(engine, model)
        self._center_comdev = None
        self.link_special_effects = []

    def add_center_comdev(self, comdev):
        self._center_comdev = comdev
        self._comdevs.add(comdev)
        comdev.add_network(self)


    def kill(self):
        for comdev in self._comdevs:
            comdev.remove_network(self)
        for link in self.link_special_effects:
            core.special_effect.LinkEffect.kill(self.engine, link[0], link[1])
        self._center_comdev = None

    def add_comdev(self, comdev):
        if self._center_comdev is None:
            self.engine.log_error("请先加载星型网络中心设备")
        else:
            self._comdevs_linked[(self._center_comdev, comdev)] = False
            self._comdevs.add(comdev)
            comdev.add_network(self)
            core.special_effect.LinkEffect.gen(self.engine, self._center_comdev.unit.name, comdev.unit.name)
            self.link_special_effects.append(
                [self.engine.render_data[self._center_comdev.unit.name].entity_id, 
                self.engine.render_data[comdev.unit.name].entity_id])
            # print('link', self._center_comdev.unit.name, comdev.unit.name)

    def check_isin_net(self, comdev1, comdev2):
        """
        """
        res = super().check_isin_net(comdev1, comdev2)
        if not res:
            res1 = super().check_isin_net(comdev1, self._center_comdev)
            res2 = super().check_isin_net(comdev2, self._center_comdev)
            if res1 and res2:
                res = True
        return res

    def check_connect(self, comdev1, comdev2):
        """
        """
        res, links = super().check_connect(comdev1, comdev2)
        if res < 0:
            res1, links1 = super().check_connect(comdev1, self._center_comdev)
            res2, links2 = super().check_connect(comdev2, self._center_comdev)
            if res1 >= 0 and res2 >= 0:
                res = res1 + res2
                links = links1 + links2
        return res, links

    def _draw(self, ax=None, mode="draw"):
        """
        """
        items = []
        if self.engine.render_config["network"]:
            if self._center_comdev is not None:  
                circle = alg.shape.Circle(self._center_comdev.coords[:2], self.attr.dis)
                if mode == "draw":
                    circle.plot(ax, "g--", linewidth=1)
                else:
                    item = circle.fillSymbol(color="green")
                    items.append(item)
        return items

    def draw(self, ax):
        self._draw(ax)

    def drawSymbol(self):
        return self._draw(mode="symbol")


def local_date_to_utc_date(str_local_date: str) -> str:
    '''
    '''
    local_date = datetime.strptime(str_local_date, "%Y-%m-%d %H:%M:%S")
    utc_tz = tz.UTC

    utc_date = local_date.astimezone(utc_tz)
    str_utc_date = utc_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    return str_utc_date


class SatelliteNetwork(core.arch.Network):
    """
    """

    def __init__(self, engine, model):
        super().__init__(engine, model)
        # 记录星网返回数据
        self._comdevs_state = {}

    def check_connect(self, comdev1, comdev2):
        """
        """
        if (comdev1, comdev2) in self._comdevs_linked and self._comdevs_linked[(comdev1, comdev2)]:
            return self._comdevs_state[(comdev1, comdev2)]["delay"], [[comdev1, comdev2]]
        elif (comdev2, comdev1) in self._comdevs_linked and self._comdevs_linked[(comdev2, comdev1)]:
            return self._comdevs_state[(comdev2, comdev1)]["delay"], [[comdev2, comdev1]]
        else:
            return -1, []

    def _check_linked(self):
        input_param = {
            "simId": self.engine.name,
            "time": local_date_to_utc_date(self.engine.ymdhms),
            "platforms": None,
            "env": {}
        }
        platforms = []
        for comdev in self._comdevs:
            unit = comdev.unit
            x, y, z = unit.coords
            lng, lat = self.engine.xy2lnglat(x, y)
            platforms.append({"id": unit.name, "lng": lng, "lat": lat, "height": z, "antennaType": 1})
        input_param["platforms"] = platforms

        async def get_communication_status():
            str_param = json.dumps(input_param)
            param_bytes = str_param.encode()
            res = await self.engine.nats_client.request("satellite_status", param_bytes)
            data = res.data.decode()
            return json.loads(data)

        loop = asyncio.get_event_loop()
        try:
            response = loop.run_until_complete(get_communication_status())
            all_link_state = response["allLinkState"]
            for comdev1, comdev2 in self._comdevs_linked.keys():
                key1 = f"{comdev1.unit.name}-{comdev2.unit.name}"
                key2 = f"{comdev2.unit.name}-{comdev1.unit.name}"

                if key1 in all_link_state and all_link_state[key1]:
                    self._comdevs_state[(comdev1, comdev2)] = all_link_state[key1]
                    if not self._comdevs_linked[(comdev1, comdev2)]:
                        self._comdevs_linked[(comdev1, comdev2)] = True
                elif key2 in all_link_state and all_link_state[key2]:
                    self._comdevs_state[(comdev1, comdev2)] = all_link_state[key2]
                    if not self._comdevs_linked[(comdev1, comdev2)]:
                        self._comdevs_linked[(comdev1, comdev2)] = True
                else:
                    self._comdevs_state[(comdev1, comdev2)] = None
                    if self._comdevs_linked[(comdev1, comdev2)]:
                        self._comdevs_linked[(comdev1, comdev2)] = False
            # loop.close()
        except:
            pass

    def implement(self):
        self._add_state("CHECK", self._check_linked, repeat=30, right_now=True)
        self._add_state("DEAD", lambda: None, repeat_ms=0)
        self._add_transfer("UNIFINED", "CHECK", lambda: True)
