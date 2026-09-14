
import os
import time
import sys
import signal


import numpy as np
import cv2
from PIL import ImageGrab


class ScreenVideo(object):
    """ 录屏工具
    """
    def __init__(self, engine, save_path, fps=2):
        self.engine = engine
        self.fps = fps # 帧率
        self.time_delay = 1/self.fps #s,录制间隔
        assert os.path.isabs(save_path), "必须为绝对路径"
        self.save_file = os.path.join(save_path, "sim_screenvedio.avi")
        self.video = cv2.VideoWriter(self.save_file, cv2.VideoWriter_fourcc(*'XVID'),
                                        fps, ImageGrab.grab().size)
        
    def record(self):
        time.sleep(2)
        while True:
            if not self.engine.isactive:
                break
            im = ImageGrab.grab()
            imm = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
            self.video.write(imm)
            time.sleep(self.time_delay)

    def release(self):
        self.video.release()
        cv2.destroyAllWindows()


def capture(engine, save_path, fps=1):
    screenvideo = ScreenVideo(engine, save_path, fps)
    # signal.signal(signal.SIGTERM, screenvideo.release)
    # print("xxxx")
    screenvideo.record()
    screenvideo.release()