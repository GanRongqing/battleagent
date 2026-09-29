# -*- coding: utf-8 -*-
"""TrackHistory — legal, append-only observation history for one target."""
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class TrackHistory:
    track_id: str
    samples: List[Tuple[float, float, float]] = field(default_factory=list)  # (t, x, y)

    def add(self, t, x, y):
        self.samples.append((float(t), float(x), float(y)))
        if len(self.samples) > 200:
            self.samples = self.samples[-200:]

    def latest(self):
        return self.samples[-1] if self.samples else None

    def velocity(self):
        """Recent estimated velocity (last two samples), else (0,0)."""
        if len(self.samples) < 2:
            return (0.0, 0.0)
        (t0, x0, y0), (t1, x1, y1) = self.samples[-2], self.samples[-1]
        dt = t1 - t0
        if dt <= 0:
            return (0.0, 0.0)
        return ((x1 - x0) / dt, (y1 - y0) / dt)

    def recent_velocity(self, n=3):
        if len(self.samples) < 2:
            return (0.0, 0.0)
        seg = self.samples[-(n + 1):]
        (t0, x0, y0) = seg[0]
        (t1, x1, y1) = seg[-1]
        dt = t1 - t0
        if dt <= 0:
            return (0.0, 0.0)
        return ((x1 - x0) / dt, (y1 - y0) / dt)

    def recent_turn_rate(self, n=4):
        """Recent heading turn rate (deg/s); 0 if insufficient evidence."""
        import math
        if len(self.samples) < 3:
            return 0.0
        seg = self.samples[-(n + 1):]
        heads = []
        for i in range(1, len(seg)):
            dt = seg[i][0] - seg[i - 1][0]
            if dt <= 0:
                continue
            dx = seg[i][1] - seg[i - 1][1]
            dy = seg[i][2] - seg[i - 1][2]
            if abs(dx) + abs(dy) < 1e-6:
                continue
            heads.append((seg[i][0], math.degrees(math.atan2(dy, dx))))
        if len(heads) < 2:
            return 0.0
        (t0, h0), (t1, h1) = heads[0], heads[-1]
        dt = t1 - t0
        if dt <= 0:
            return 0.0
        return ((h1 - h0 + 180) % 360 - 180) / dt
