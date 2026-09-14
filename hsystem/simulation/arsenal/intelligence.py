import numpy as np
import collections

from .. import algorithm as alg
from .. import core
from .. import message
from .. import arsenal as asn

class Intelligence(core.arch.Component):
    """ 情报处理仿真模块 """

    def __init__(self, unit, model):
        super().__init__(unit, model)
        self._superior_intels = set()
        self._junior_intels = set()
        # self._consumers = set() # 情报消费者
        self._consumers = dict()
        self.radar_tracks = set()
        self.sonar_tracks = set()
        self.magnetic_tracks = set()
        self.satellite_tracks = set()
        self.photoelectric_tracks = set()

    def add_superior_intel(self, intel):
        self._superior_intels.add(intel)

    def add_consumer(self, consumer, target=None):
        # self._consumers.add(consumer)
        if consumer not in self._consumers:
            if target is None:
                self._consumers[consumer] = set()
            else:
                self._consumers[consumer] = set([target])
        else:
            if target is None:
                self._consumers[consumer] = set()
            else:
                self._consumers[consumer].add(target)

    def remove_consumer(self, consumer, target=None):
        assert consumer in self._consumers
        if target is not None:
            assert target in self._consumers[consumer]
            self._consumers[consumer].remove(target)
            if not self._consumers[consumer]:
                # 为空set，此时表示没有可以分发的目标对象，应移除
                del self._consumers[consumer] # 移除
        else:
            if consumer in self._consumers:
                del self._consumers[consumer] # 移除

    @property
    def targets(self):
        return self.radar_targets + self.sonar_targets + self.magnetic_targets + self.satellite_targets + self.photoelectric_targets

    @property
    def radar_targets(self):
        return [x.target for x in self.radar_tracks if x.target.isactive]

    @property
    def sonar_targets(self):
        return [x.target for x in self.sonar_tracks if x.target.isactive]

    @property
    def magnetic_targets(self):
        return [x.target for x in self.magnetic_tracks if x.target.isactive]

    @property
    def satellite_targets(self):
        return [x.target for x in self.satellite_tracks if x.target.isactive]

    @property
    def photoelectric_targets(self):
        return [x.target for x in self.photoelectric_tracks if x.target.isactive]

    @property
    def radar_target_source(self):
        return {x.target: x.sensor for x in self.radar_tracks if x.target.isactive}

    def get_radar_track(self, target):
        for track in self.radar_tracks:
            if track.target is target:
                return track
        return None

    def get_sonar_track(self, target):
        for track in self.sonar_tracks:
            if track.target is target:
                return track
        return None

    def get_magnetic_track(self, target):
        for track in self.magnetic_tracks:
            if track.target is target:
                return track
        return None

    def get_satellite_track(self, target):
        for track in self.satellite_tracks:
            if track.target is target:
                return track
        return None

    def get_photoelectric_track(self, target):
        for track in self.photoelectric_tracks:
            if track.target is target:
                return track
        return None

    def _work(self):
        self.radar_tracks = set( [x for x in self.radar_tracks if self.engine.tick - x.when <= 1000*self.attr["radar_update_time"]] )
        self.sonar_tracks = set( [x for x in self.sonar_tracks if self.engine.tick - x.when <= 1000*self.attr["sonar_update_time"] ] )
        self.magnetic_tracks = set( [x for x in self.magnetic_tracks if self.engine.tick - x.when <= 1000*self.attr["magnetic_update_time"] ] )
        self.satellite_tracks = set( [x for x in self.satellite_tracks if self.engine.tick - x.when <= 1000*self.attr["satellite_update_time"] ] )
        self.photoelectric_tracks = set( [x for x in self.photoelectric_tracks if self.engine.tick - x.when <= 1000*self.attr["photoelectric_update_time"] ] )
        if self.attr.send_mode == "period":
            for track in self.radar_tracks:
                content = core.message.MsgTrack(track)
                for intel in self._superior_intels:
                    self._send_msg(intel, content)
                self._send_consumers(content)
                    
            for track in self.sonar_tracks:
                content = core.message.MsgTrack(track)
                for intel in self._superior_intels:
                    self._send_msg(intel, content)
                self._send_consumers(content)
            
            for track in self.satellite_tracks:
                content = core.message.MsgTrack(track)
                for intel in self._superior_intels:
                    self._send_msg(intel, content)
                self._send_consumers(content)

    def _process(self, msg):
        track = msg.content.track
        if isinstance(track, message.track.RadarTrack):
            targets = [ x.target for x in self.radar_tracks ]
            if track.target not in targets:
                self.radar_tracks.add(track)
            else:
                temp = [x for x in self.radar_tracks if x.target is track.target]
                for x in temp:
                    self.radar_tracks.remove(x)
                self.radar_tracks.add(track)
        elif isinstance(track, message.track.SonarTrack):
            targets = [ x.target for x in self.sonar_tracks ]
            if track.target not in targets:
                self.sonar_tracks.add(track)
            else:
                temp = [x for x in self.sonar_tracks if x.target is track.target]
                for x in temp:
                    self.sonar_tracks.remove(x)

                self.sonar_tracks.add(track)
        elif isinstance(track, message.track.MagneticDetectorTrack):
            targets = [ x.target for x in self.magnetic_tracks]
            if track.target not in targets:
                self.magnetic_tracks.add(track)
            else:
                temp = [x for x in self.magnetic_tracks if x.target is track.target]
                for x in temp:
                    self.magnetic_tracks.remove(x)
                self.magnetic_tracks.add(track)

        elif isinstance(track, message.track.SatelliteTrack):
            targets = [x.target for x in self.satellite_tracks]
            if track.target not in targets:
                self.satellite_tracks.add(track)
            else:
                temp = [x for x in self.satellite_tracks if x.target is track.target]
                for x in temp:
                    self.satellite_tracks.remove(x)
                self.satellite_tracks.add(track)
            if self.engine.cache.get("Tag","Error") == "defe":
                if (not isinstance(self.unit, asn.satellite.Satellite)) and (self.unit.group == "RED"):
                    print(f"Time {self.engine.time}, {self.unit.name}收到来自{msg.src.unit.name}的目指信息")
        elif isinstance(track, message.track.PhotoelectricTrack):
            targets = [ x.target for x in self.photoelectric_tracks]
            if track.target not in targets:
                self.photoelectric_tracks.add(track)
            else:
                temp = [x for x in self.photoelectric_tracks if x.target is track.target]
                for x in temp:
                    self.photoelectric_tracks.remove(x)
                self.photoelectric_tracks.add(track)

        if self.attr.send_mode == "rightnow":
            content = core.message.MsgTrack(track)
            for intel in self._superior_intels:
                self._send_msg(intel, content)
            self._send_consumers(content)

    def _send_consumers(self, content: core.message.MsgTrack):
        for consumer, csm_set in self._consumers.items():
            if csm_set:
                if content.track.target in csm_set:
                    self._send_msg(consumer, content)
            else:
                # 为空set，则不检查，都发
                self._send_msg(consumer, content)

    def implement(self):
        self._add_state("WORK", self._work, repeat=self.attr["period"])
        self._add_transfer("FREE",  "WORK", lambda: True)
        self._add_handler("MsgTrack", self._process)
        return self

    def check(self):
        assert hasattr(self.attr, "radar_update_time")
        assert hasattr(self.attr, "sonar_update_time")
        assert hasattr(self.attr, "magnetic_update_time")
        assert hasattr(self.attr, "satellite_update_time")
        assert hasattr(self.attr, "photoelectric_update_time")
        assert hasattr(self.attr, "delay_time")
        assert hasattr(self.attr, "send_mode")

    def _draw(self, ax=None, mode="draw"):
        """
        mode = "draw" or "qt"
        """
        items = []
        if self.engine.render_config["intels_relation"]:
            x0, y0, z0 = self.coords
            # 绘制信息上报关系
            for intel in self._superior_intels:
                x1, y1, z1 = intel.coords
                # 绘制箭头
                if mode == "draw":
                    ax.arrow(x0, y0, x1-x0, y1-y0, linestyle="--", shape="full", fc="lime", ec="lime")
            # 绘制消费关系
            for con in self._consumers.keys():
                x1, y1, z1 = con.coords
                # 绘制箭头
                if mode == "draw":
                    ax.arrow(x0, y0, x1-x0, y1-y0, linestyle="--", shape="full", fc="lime", ec="lime")
        return items