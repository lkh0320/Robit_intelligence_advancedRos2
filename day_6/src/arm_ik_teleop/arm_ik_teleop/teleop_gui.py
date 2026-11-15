"""엔드이펙터 IK 텔레옵 버튼 GUI (Tk)

왼쪽 링  : +X (위) / -X (아래) / +Y (왼쪽) / -Y (오른쪽),  Z+ / Z- 버튼
오른쪽 링: pitch+ (위) / pitch- (아래) / yaw+ (왼쪽) / yaw- (오른쪽),  roll- / roll+ 버튼
버튼을 누르고 있으면 계속 움직임. 창이 선택돼 있으면 ik_core 키보드 키도 됨.

FK (URDF) vs IK 목표 비교는 이 노드를 띄운 터미널에 출력된다.
ROS 파라미터: lin_speed [mm/s] (기본 50), ang_speed [deg/s] (기본 20)
"""
import math
import threading
import tkinter as tk

import numpy as np
import rclpy
from rclpy.executors import ExternalShutdownException, SingleThreadedExecutor

from arm_ik_teleop.ik_core import IkKeyboardTeleop, rot

TICK_MS = 50
BG, RING, HOT = "#f4f4f4", "#dfe6ee", "#7fb2e5"
LABEL_FG = "#c0392b"


class RingPad(tk.Canvas):
    """4칸(위/왼쪽/아래/오른쪽)으로 나눈 도넛 버튼. on_press(seg) / on_release()"""
    SEGS = {"top": 45, "left": 135, "bottom": 225, "right": 315}

    def __init__(self, master, labels, center, on_press, on_release, R=95, r=42):
        size = 2 * R + 10
        super().__init__(master, width=size, height=size, bg=BG, highlightthickness=0)
        self.c, self.R, self.r = size / 2, R, r
        self.on_press, self.on_release = on_press, on_release
        self.items = {}
        c = self.c
        for seg, start in self.SEGS.items():
            self.items[seg] = self.create_arc(c - R, c - R, c + R, c + R, start=start, extent=90,
                                              style=tk.PIESLICE, fill=RING, outline="#333", width=2)
        self.create_oval(c - r, c - r, c + r, c + r, fill=BG, outline="#333", width=2)
        self.create_text(c, c, text=center, font=("Sans", 11, "bold"), fill="#555")
        m = (R + r) / 2
        pos = {"top": (c, c - m), "bottom": (c, c + m), "left": (c - m, c), "right": (c + m, c)}
        for seg, (x, y) in pos.items():
            self.create_text(x, y, text=labels[seg], font=("Sans", 11, "bold"), fill=LABEL_FG)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.hot = None

    def _press(self, ev):
        dx, dy = ev.x - self.c, self.c - ev.y
        d = math.hypot(dx, dy)
        if not (self.r <= d <= self.R):
            return
        a = math.degrees(math.atan2(dy, dx)) % 360
        seg = "right" if a < 45 or a >= 315 else "top" if a < 135 else "left" if a < 225 else "bottom"
        self.hot = seg
        self.itemconfig(self.items[seg], fill=HOT)
        self.on_press(seg)

    def _release(self, _ev):
        if self.hot:
            self.itemconfig(self.items[self.hot], fill=RING)
            self.hot = None
        self.on_release()


class App:
    def __init__(self, node):
        self.node = node
        node.declare_parameter("lin_speed", 50.0)   # mm/s
        node.declare_parameter("ang_speed", 20.0)   # deg/s
        self.lin_speed = node.get_parameter("lin_speed").value / 1000.0
        self.ang_speed = math.radians(node.get_parameter("ang_speed").value)
        self.active = None
        self.failed = False
        self.root = root = tk.Tk()
        root.title("Eclipse arm IK teleop")
        root.configure(bg=BG)

        pads = tk.Frame(root, bg=BG)
        pads.pack(padx=10, pady=10)
        RingPad(pads, {"top": "+X", "bottom": "-X", "left": "+Y", "right": "-Y"}, "XY",
                lambda s: self.start({"top": ("p", 0, 1), "bottom": ("p", 0, -1),
                                      "left": ("p", 1, 1), "right": ("p", 1, -1)}[s]),
                self.stop).grid(row=0, column=0, padx=6)
        zbox = tk.Frame(pads, bg=BG)
        zbox.grid(row=0, column=1, padx=(4, 24))
        self.hold_button(zbox, "Z +", ("p", 2, 1)).pack(fill="x")
        self.hold_button(zbox, "Z -", ("p", 2, -1)).pack(fill="x")
        RingPad(pads, {"top": "pitch +", "bottom": "pitch -", "left": "yaw +", "right": "yaw -"}, "RPY",
                lambda s: self.start({"top": ("r", "y", 1), "bottom": ("r", "y", -1),
                                      "left": ("r", "z", 1), "right": ("r", "z", -1)}[s]),
                self.stop).grid(row=0, column=2, padx=6)
        rbox = tk.Frame(pads, bg=BG)
        rbox.grid(row=0, column=3, padx=4)
        self.hold_button(rbox, "roll -", ("r", "x", -1)).pack(side="left")
        self.hold_button(rbox, "roll +", ("r", "x", 1)).pack(side="left")
        tk.Button(root, text="Reset", command=node.reset, width=8).pack(pady=(0, 10))

        root.bind("<KeyPress>", lambda ev: node.on_key(ev.char.lower()) if ev.char else None)
        root.protocol("WM_DELETE_WINDOW", root.quit)
        root.after(TICK_MS, self.tick)

    def hold_button(self, parent, text, move):
        b = tk.Label(parent, text=text, width=7, height=3, bg=RING, relief="raised", bd=2,
                     font=("Sans", 11, "bold"), fg=LABEL_FG)
        b.bind("<ButtonPress-1>", lambda _e: (b.config(bg=HOT, relief="sunken"), self.start(move)))
        b.bind("<ButtonRelease-1>", lambda _e: (b.config(bg=RING, relief="raised"), self.stop()))
        return b

    def start(self, move):
        self.active = move
        self.failed = False
        self.step(move)

    def stop(self):
        self.active = None

    def step(self, move):
        kind, axis, sign = move
        dt = TICK_MS / 1000.0
        if kind == "p":
            v = np.zeros(3)
            v[axis] = sign * self.lin_speed * dt
            ok, ep, er = self.node.apply_move("p", v)
        else:
            ok, ep, er = self.node.apply_move("r", rot(axis, sign * self.ang_speed * dt))
        if not ok and not self.failed:  # 한 번 누를 때 한 번만 출력
            self.node.report_fail(f"{kind}{axis}{'+' if sign > 0 else '-'}", ep, er)
        self.failed = not ok

    def tick(self):
        if self.active:
            self.step(self.active)
        self.root.after(TICK_MS, self.tick)


def main():
    rclpy.init()
    node = IkKeyboardTeleop("ik_teleop_gui")
    ex = SingleThreadedExecutor()
    ex.add_node(node)
    def spin():
        try:
            ex.spin()
        except ExternalShutdownException:
            pass

    spin_thread = threading.Thread(target=spin, daemon=True)
    spin_thread.start()
    app = App(node)
    try:
        app.root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        # 종료 전에 spin 스레드 먼저 정리 (안 하면 종료할 때 C++ 쪽에서 abort 남)
        if rclpy.ok():
            rclpy.shutdown()
        spin_thread.join(timeout=2.0)
        ex.shutdown()
        node.destroy_node()
        try:
            app.root.destroy()
        except tk.TclError:
            pass


if __name__ == "__main__":
    main()
