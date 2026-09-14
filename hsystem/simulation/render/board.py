import logging
import tkinter as tk 
import shutil
import os
import time
import threading

import numpy as np
import matplotlib as mpl 
mpl.use("Agg")
mpl.rcParams["font.sans-serif"] = ["SimHei"]
mpl.rcParams["axes.unicode_minus"] = False
import matplotlib.figure as figure
import matplotlib.pyplot as plt
import mpl_toolkits.mplot3d.axes3d as axes3d
import matplotlib.backends.backend_tkagg as backend
import mpl_toolkits

import simulation.core as core
import simulation.arsenal as asn


class WidgetLogger(logging.Handler):
    def __init__(self, widget):
        super(WidgetLogger, self).__init__()
        self.widget = widget 
        self.widget.config(state="disable")
        self.widget.tag_config("WARNING", foreground="red")

    def emit(self, record):
        self.widget.config(state="normal")
        self.widget.insert(tk.END, self.format(record) + "\n")
        self.widget.see(tk.END)
        self.widget.config(state="disable")


class Topview(tk.Frame):
    CNT = 0
    def __init__(self, master, engine, v, red_flag, blue_flag, active_flag):
        super(Topview, self).__init__(master)
        self.master = master 
        self.engine = engine
        self.v = v
        self.red_flag = red_flag
        self.blue_flag = blue_flag
        self.active_flag = active_flag
        self.fig = figure.Figure()
        # self.canvas = backend.FigureCanvasAgg(self.fig, self.master)
        self.canvas = backend.FigureCanvasTkAgg(self.fig, self.master)
        self._is_init = False # fig 和 ax 是否初始化
        self._mode = "XY" #三种模式，分别为"XY","XZ", "XYZ"
        self._terrain_xy = None
        self._terrain_xyz = None
        self.draw()

    def set_mode(self, mode):
        assert mode in ["XY", "XZ", "XYZ"]
        self._mode = mode
        self._is_init = False
        
    def draw(self, interval=20):
        # if not self.engine.isactive:
        #     self.master.destroy()
        try:
            value = self.v.get()
        except:
            import pdb; pdb.set_trace()
        if value == 1:
            if self._mode != "XY":
                self.set_mode("XY")
        elif value == 2:
            if self._mode != "XZ":
                self.set_mode("XZ")
        else:
            if self._mode != "XYZ":
                self.set_mode("XYZ")

        if not self._is_init:
            self._is_init = True
            if self.fig.axes:
                self.fig.delaxes(self.ax)
            if self._mode == "XY":
                self.fig.add_subplot(1, 1, 1, label="sim")
                self.fig.subplots_adjust(top=0.922,bottom=0.077,left=0.039,right=0.971,hspace=0.344,wspace=0.2)
                self.ax = self.fig.gca()
                if self.engine.render_config["equal"]:
                    self.ax.set_aspect("equal")
                else:
                    self.ax.set_aspect("auto")
                if self.engine.render_config["xlim"]:
                    self.ax.set_xlim(self.engine.render_config["xlim"])
                if self.engine.render_config["ylim"]:
                    self.ax.set_ylim(self.engine.render_config["ylim"])
                self.ax.set_ylabel("")
                if self.engine.sim_config["terrain"]:
                    self._terrain_xy = self.engine.env.terrain.draw(self.ax)
            elif self._mode == "XZ":
                self.fig.add_subplot(1, 1, 1, label="sim")
                self.fig.subplots_adjust(top=0.922,bottom=0.077,left=0.039,right=0.971,hspace=0.344,wspace=0.2)
                self.ax = self.fig.gca()
                if self.engine.render_config["equal"]:
                    self.ax.set_aspect("equal")
                else:
                    self.ax.set_aspect("auto")
                if self.engine.render_config["xlim"]:
                    self.ax.set_xlim(self.engine.render_config["xlim"])
                if self.engine.render_config["zlim"]:
                    self.ax.set_ylim(self.engine.render_config["zlim"])
                self.ax.set_ylabel("高度(m)")
            else:
                self.fig.add_subplot(1, 1, 1, projection='3d', label="sim")
                self.ax = self.fig.gca()
                if self.engine.render_config["xlim"]:
                    self.ax.set_xlim(self.engine.render_config["xlim"])
                if self.engine.render_config["ylim"]:
                    self.ax.set_ylim(self.engine.render_config["ylim"])
                if self.engine.render_config["zlim"]:
                    self.ax.set_zlim(self.engine.render_config["zlim"])
                self.ax.set_ylabel("")
                if self.engine.sim_config["terrain"]:
                    self._terrain_xyz = self.engine.env.terrain.draw3D(self.ax)
        if self._is_init:
            self.ax.collections = []
            self.ax.texts = []
            self.ax.lines = []
            self.ax.patches = []
            if self._terrain_xy is not None and self._mode == "XY" and self.engine.render_config["terrain"]:
                self.ax.collections.extend(self._terrain_xy)
            if self._terrain_xyz is not None and self._mode == "XYZ" and self.engine.render_config["terrain"]:
                self.ax.collections.extend(self._terrain_xyz)
            # hms = time.strftime("%H:%M:%S", time.strptime(time.ctime(self.engine.time)))
            # text = "仿真时间:" + hms
            secs = self.engine.tick * 1e-3
            text = "仿真时间:" + str(int(secs)) + "s"
            text += "  " + "仿真倍率:" + f"{self.engine.ratio:.2f}"
            text += "  " + "时间:" + self.engine.ymdhms
            text += "  " + "风速(m/s):" + str(self.engine.env.wind.speed)
            text += "  " + "风向(度):" + str(self.engine.env.wind.direction)
            text += "  " + "太阳高度角(度):" + f"{self.engine.env.sun_pitch:.1f}"
            text += "  " + "太阳方位角(度):" + f"{self.engine.env.sun_azimuth:.1f}"
            text += "  " + "海况:" + self.engine.env.sea_state
            text += "  " + "水文条件:" + self.engine.env.water

            def filter_fun(u):
                if u.is_at_home and u.__class__.__name__ != "DependentPlatform":
                    return False
                if self.active_flag.get():
                    cond1 = u.isactive
                else:
                    cond1 = True
                if self.red_flag.get() and self.blue_flag.get():
                    cond2 = True
                elif self.red_flag.get():
                    cond2 = (u.group == "RED")
                elif self.blue_flag.get():
                    cond2 = (u.group == "BLUE")
                else:
                    cond2 = False
                return cond1 and cond2
                
            if self._mode == "XY":
                for network in self.engine.networks():
                    network.draw(self.ax)
                for o in self.engine.units(filter_fun):
                    o.draw(self.ax)
                self.engine.lock.acquire()
                # for o in self.engine.special_effects:
                #     if o.isactive:
                #         o.draw(self.ax)
                for name, data in self.engine.render_data.items():
                    if data.isactive:
                        core.CLASS[data.class_].draw(self.engine, name, ax=self.ax)
                self.engine.lock.release()
                for o in self.engine.env_effects:
                    if o.isactive:
                        o.draw(self.ax)
                x = self.ax.get_xlim()[0]
                y = self.ax.get_ylim()[1]
                xlim = self.ax.get_xlim()[1] - self.ax.get_xlim()[0]
                ylim = self.ax.get_ylim()[1] - self.ax.get_ylim()[0]
                self.ax.text(x, y+0.01*ylim, text)
                self.engine.env.wind.draw(self.ax, x+0.02*xlim, y-0.02*ylim)
                if self.engine.render_config["equal"]:
                    self.ax.set_aspect("equal")
                else:
                    self.ax.set_aspect("auto")
            elif self._mode == "XZ":
                # for o in self.engine.actives():
                for o in self.engine.units(filter_fun):
                    o.drawXz(self.ax)
                x = self.ax.get_xlim()[0]
                y = self.ax.get_ylim()[1]
                xlim = self.ax.get_xlim()[1] - self.ax.get_xlim()[0]
                ylim = self.ax.get_ylim()[1] - self.ax.get_ylim()[0]
                self.ax.text(x, y+0.01*ylim, text)
                if self.engine.render_config["equal"]:
                    self.ax.set_aspect("equal")
                else:
                    self.ax.set_aspect("auto")
            else:
                # for o in self.engine.actives():
                for o in self.engine.units(filter_fun):
                    o.draw3D(self.ax)           
            
            self.canvas.draw()
            Topview.CNT += 1
            self.master.after(interval, self.draw)

    def pack(self, *args, **kwargs):
        self.canvas.get_tk_widget().pack(*args, **kwargs)


class TargetDialog(tk.Toplevel):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.title("设置典型目标信息")

        row1 = tk.Frame(self)
        # row1.pack(fill="x")
        row1.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.NO)
        tk.Label(row1, text="目标RCS(m^2)", width=20).pack(side=tk.LEFT)
        self.rcs = tk.DoubleVar()
        tk.Entry(row1, textvariable=self.rcs, width=10).pack(side=tk.LEFT)
        # tk.Spinbox(row1, textvariable=self.rcs, width=10).pack(side=tk.LEFT)
        self.rcs.set(self.engine.render_config["target"]["rcs"])

        row2 = tk.Frame(self)
        # row2.pack(fill="x")
        row2.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.NO)
        tk.Label(row2, text="目标高度(m)", width=20).pack(side=tk.LEFT)
        self.height = tk.DoubleVar()
        tk.Entry(row2, textvariable=self.height, width=10).pack(side=tk.LEFT)
        # tk.Spinbox(row2, textvariable=self.height, width=10).pack(side=tk.LEFT)
        self.height.set(self.engine.render_config["target"]["height"])

        row3 = tk.Frame(self)
        # row3.pack(fill="x")
        row3.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.NO)
        tk.Label(row3, text="目标速度(m/s)", width=20).pack(side=tk.LEFT)
        self.speed = tk.DoubleVar()
        tk.Entry(row3, textvariable=self.speed, width=10).pack(side=tk.LEFT)
        # tk.Spinbox(row3, textvariable=self.speed, width=10).pack(side=tk.LEFT)
        self.speed.set(self.engine.render_config["target"]["speed"])

        row4 = tk.Frame(self)
        # row4.pack(fill="x")
        row4.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.NO)
        tk.Button(row4, text="应用", command=self.apply, width=10).pack(side=tk.LEFT)
        tk.Button(row4, text="关闭", command=self.close, width=10).pack(side=tk.RIGHT)

    def apply(self):
        self.engine.render_config["target"].update({"rcs":self.rcs.get(), "speed":self.speed.get(), "height":self.height.get()})

    def close(self):
        self.destroy()


class UnitSelectDialog(tk.Toplevel):
    """ 单元选择的弹窗 """
    def __init__(self, engine, key="history_points_units", title="选择显示航迹的目标"):
        super().__init__()
        self.engine = engine
        self.key= key
        self.unit_names = engine.render_config[key]
        self.unit_names_dict = {} # 与self.unit_names等价的字典，存在则为True
        self.unit_names_cbs = {} # 与self.unit_names_dict等价的记录checkbutton的字典
        self.all_unit_names = self.get_all_unit_names()

        self.title(title)
        row1 = tk.Frame(self)
        row1.pack(side=tk.TOP, anchor=tk.N,  fill=tk.X, expand=tk.YES)
        tk.Button(row1, text="全选", command=self.select_all, width=10).pack(side=tk.LEFT)
        tk.Button(row1, text="全不选", command=self.select_none, width=10).pack(side=tk.RIGHT)
        row2 = tk.Frame(self)
        row2.pack(side=tk.TOP, anchor=tk.N,  fill=tk.X, expand=tk.YES)
        for unit_name in self.all_unit_names:
            cb = self.generate_checkbutton(row2, unit_name)
            cb.pack(side=tk.TOP, anchor=tk.W)
        row3 = tk.Frame(self)
        row3.pack(side=tk.BOTTOM, anchor=tk.N,  fill=tk.X, expand=tk.YES)
        tk.Button(row3, text="应用", command=self.apply, width=10).pack(side=tk.LEFT)
        tk.Button(row3, text="关闭", command=self.close, width=10).pack(side=tk.RIGHT)

    def generate_checkbutton(self, parent, unit_name):
        if self.unit_names == "all":
            self.unit_names_dict[unit_name] = True
        else:
            if unit_name in self.unit_names:
                self.unit_names_dict[unit_name] = True
            else:
                self.unit_names_dict[unit_name] = False
        checkbutton = tk.Checkbutton(parent, text=unit_name, command=lambda: self.unit_names_dict.update({unit_name: not self.unit_names_dict[unit_name]}))
        self.unit_names_cbs[unit_name] = checkbutton
        if self.unit_names_dict[unit_name]:
            checkbutton.select() # 不会触发command，只有手动点击时会触发
        else:
            checkbutton.deselect() # 不会触发command，只有手动点击时会触发
        return checkbutton

    def get_all_unit_names(self):
        """ 潜在可选的所有unit name """
        if self.key == "history_points_units":
            # 所有非is_at_home的units
            return [unit.name for unit in self.engine.units() if not unit.is_at_home]
        elif self.key == "component_render_units":
            # 有所的非子平台, 除了DependentPlatform
            units = [unit.name for unit in self.engine.units()  
                        if unit.home_unit is None or isinstance(unit, core.arch.DependentPlatform)]
            return units
        else:
            raise RuntimeError(f"未知的key:{self.key}")

    def select_all(self):
        for unit_name, cb in self.unit_names_cbs.items():
            if not self.unit_names_dict[unit_name]:
                self.unit_names_dict[unit_name] = True
                cb.select() # 不会触发command，只有手动点击时会触发
        self.unit_names = "all"

    def select_none(self):
        for unit_name, cb in self.unit_names_cbs.items():
            if self.unit_names_dict[unit_name]:
                self.unit_names_dict[unit_name] = False
                cb.deselect() # 不会触发command，只有手动点击时会触发
        self.unit_names = []

    def apply(self):
        if self.unit_names == "all":
            pass  
        else:
            self.unit_names = [unit_name for unit_name, tag in self.unit_names_dict.items() if tag] 
        self.engine.render_config.update({self.key: self.unit_names})

    def close(self):
        self.destroy()    


class Application(tk.Tk):
    def __init__(self, engine, console, log):
        """ console=True, 即控制台模式下，窗口不绘制态势图，仅显示部分控制按钮
            log=True, 在非控制台模式下，是否显示日志窗口；在控制台模式下不起作用
        """
        super(Application, self).__init__()
        self.console = console
        self.log = log
        self.wm_title("模拟平台")
        # self.configure(bg="CadetBlue")

        # 从上往下依次生成控件
        frame1 = tk.Frame(self) # 第一行
        frame2 = tk.Frame(self) # 第二行

        if not self.console:
            v = tk.IntVar()
            b1 = tk.Radiobutton(frame1, text="XY", variable=v, value=1)
            b2 = tk.Radiobutton(frame1, text="XZ", variable=v, value=2)
            b3 = tk.Radiobutton(frame1, text="XYZ", variable=v, value=3)
            v.set(1)

        button1 = tk.Button(frame1, text="暂停/启动", command=lambda: engine.pause_continue())
        def change_equal():
            engine.render_config["equal"] = not engine.render_config["equal"]
        button2 = tk.Button(frame1, text="equal/not", command=change_equal)
        if engine.ratio == "SYSTEM":
            showvalue = 500
        elif engine.ratio > 500:
            showvalue = 500
        elif engine.ratio < 1:
            showvalue = 1
        else:
            showvalue = engine.ratio
        ratio = tk.Scale(frame1, label="", from_=1, to=500, resolution=1, orient=tk.HORIZONTAL,
                command=lambda v: engine.set_ratio(float(v)))
        ratio.set(showvalue)
        button3 = tk.Button(frame1, text="终止", command=lambda: engine.set_end_time(engine.time))
        button4 = tk.Button(frame1, text="干预", command=lambda: engine.set_probe())
        button5 = tk.Button(frame1, text="设置典型目标参数", command=lambda: TargetDialog(engine))
        history_points_button = tk.Button(frame1, text="航迹显示", command=lambda: UnitSelectDialog(engine, key="history_points_units", title="选择显示航迹的目标"))
        component_render_button = tk.Button(frame1, text="组件显示", command=lambda: UnitSelectDialog(engine, key="component_render_units", title="选择绘制组件的目标"))

        red_flag = tk.IntVar()
        blue_flag = tk.IntVar()
        active_flag = tk.IntVar()
        red_check_button = tk.Checkbutton(frame1, text="红方", variable=red_flag, onvalue=1, offvalue=0)
        blue_check_button = tk.Checkbutton(frame1, text="蓝方", variable=blue_flag, onvalue=1, offvalue=0)
        active_check_button = tk.Checkbutton(frame1, text="存活", variable=active_flag, onvalue=1, offvalue=0)
        red_flag.set(1)
        blue_flag.set(1)
        active_flag.set(1)

        def generate_checkbutton(parent, text, key):
            checkbutton = tk.Checkbutton(parent, text=text, command=lambda: engine.render_config.update({key: not engine.render_config[key]}))
            if engine.render_config[key]:
                checkbutton.select() # 不会触发command，只有手动点击时会触发
            else:
                checkbutton.deselect() # 不会触发command，只有手动点击时会触发
            return checkbutton

        cbs1 = []
        cbs2 = []
        for k, vv in engine.checkbox_dict.items():
            if vv['class'] == 1:
                cb = generate_checkbutton(frame1, k, vv["name"])
                cbs1.append(cb)
            else:
                cb = generate_checkbutton(frame2, k, vv["name"])
                cbs2.append(cb)

        if not self.console:
            if self.log:
                text = tk.Text(self, height=10)
                # fmt = logging.Formatter("%(timestamp)s %(ticks)s %(message)s")
                fmt = logging.Formatter("%(timestamp)s %(levelname)s %(message)s")
                wg = WidgetLogger(text)
                wg.setFormatter(fmt)
                engine._Engine__tracer.logger.addHandler(wg)
            view = Topview(self, engine, v, red_flag, blue_flag, active_flag)
            # tool = backend.NavigationToolbar2Tk(view.canvas, self)
            tool = backend.NavigationToolbar2Tk(view.canvas, frame2)

        # 从上到下依次布局控件
        # 第一行按钮
        frame1.pack(side=tk.TOP, anchor=tk.N,  fill=tk.X, expand=tk.NO)
        if not self.console:
            b1.pack(side=tk.LEFT, fill=tk.NONE, expand=tk.NO)
            b2.pack(side=tk.LEFT, fill=tk.NONE, expand=tk.NO)
            b3.pack(side=tk.LEFT, fill=tk.NONE, expand=tk.NO)
        button1.pack(side=tk.LEFT, fill=tk.NONE, expand=tk.NO)
        button2.pack(side=tk.LEFT, fill=tk.NONE, expand=tk.NO)
        ratio.pack(side=tk.LEFT, fill=tk.NONE, expand=tk.NO)
        button3.pack(side=tk.LEFT, fill=tk.NONE, expand=tk.NO)
        button4.pack(side=tk.LEFT, fill=tk.NONE, expand=tk.NO)
        button5.pack(side=tk.LEFT, fill=tk.NONE, expand=tk.NO)
        history_points_button.pack(side=tk.LEFT, fill=tk.NONE, expand=tk.NO)
        component_render_button.pack(side=tk.LEFT, fill=tk.NONE, expand=tk.NO)

        for cb in cbs1:
            cb.pack(side=tk.RIGHT, fill=tk.NONE, expand=tk.NO)
        active_check_button.pack(side=tk.RIGHT, fill=tk.NONE, expand=tk.NO)
        blue_check_button.pack(side=tk.RIGHT, fill=tk.NONE, expand=tk.NO)
        red_check_button.pack(side=tk.RIGHT, fill=tk.NONE, expand=tk.NO)
        
        # 第二行按钮
        frame2.pack(side=tk.TOP, anchor=tk.N,  fill=tk.X, expand=tk.NO)
        if not self.console:
            tool.pack(side=tk.LEFT, fill=tk.NONE, expand=tk.NO)
        for cb in cbs2:
            cb.pack(side=tk.RIGHT, fill=tk.NONE, expand=tk.NO)
        # 第四行日志界面
        if not self.console:
            if self.log:
                text.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=tk.NO)
        # 第三行动画界面
        if not self.console:
            view.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=tk.YES)

def auto_close(app, engine):
    while True:
        time.sleep(1)
        if not engine.isactive:
            # time.sleep(10) # 很奇怪，立马销毁那么在产生新的窗体是会报错，但等待几秒待新的窗体产生后再销毁则不会报错
            app.destroy()
            return


def draw(engine, console=False, log=True):
    app = Application(engine, console, log)
    # w = app.winfo_screenwidth()
    # h = app.winfo_screenheight()
    # app.geometry("{}x{}".format(w, h))
    # app.attributes("-topmost", True)
    # app.attributes("-fullscreen", True)
    if not console:
        app.wm_state("zoomed")
    t = threading.Thread(target=auto_close, args=(app, engine))
    t.start()
    app.mainloop()