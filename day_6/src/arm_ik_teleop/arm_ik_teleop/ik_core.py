"""Eclipse 팔 IK + 키보드 엔드이펙터 텔레옵

gripper_base_link 목표 자세를 키보드로 움직이면 DH 모델로 해석적 IK를 풀어서
/ik_joint_states 로 JointState를 보낸다. robot_description/display.launch.py 의
joint_state_publisher_gui 가 source_list 로 받아서 RViz에 보여준다. (실제 모터는 안 움직임)

자세가 바뀔 때마다 IK 목표와, /robot_description URDF로 PyKDL FK를 따로 계산한 값,
그리고 둘의 차이를 터미널에 출력한다. (DH 표가 URDF와 맞는지 확인용)

시작 자세 = DH 영점(theta = 0): 링크2는 뒤로, 링크3은 그 위로 접히고, 그리퍼는 joint2 앞에서 +x 방향

키 (mani_base_link 기준 이동, mani_base_link 축 기준 회전, 회전 중심은 손끝):
    a / d : -x / +x        w / s : +z / -z        q / e : +y / -y
    u / j : +pitch / -pitch (Y축)
    h / k : +yaw   / -yaw   (Z축)
    t / g : +roll  / -roll  (X축)
    [ / ] : 스텝 줄이기 / 늘리기     r : 리셋     space : 현재 자세 출력
    Ctrl-C: 종료
"""
import math
import select
import sys
import termios
import threading
import tty
import xml.etree.ElementTree as ET

import numpy as np
import PyKDL as kdl
import rclpy
from geometry_msgs.msg import Point
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from sensor_msgs.msg import JointState
from std_msgs.msg import String
from visualization_msgs.msg import Marker, MarkerArray

# ---------------------------------------------------------------------------
# DH 모델 (standard DH, m / rad), 프레임 {0} = arm_joint1 원점
# DH 영점(theta = 0) = 접힌 자세 (링크2 뒤로, 링크3 그 위로, 그리퍼 앞으로)
# URDF 관절값 q = theta + Q_SHIFT :  q2 = theta2 - 90도,  q3 = theta3 + 180도
# ---------------------------------------------------------------------------
PHI = math.atan2(26.857, 416.012)                     # 링크2 기울기 3.694도
DH = [  # (d, theta_offset, a, alpha)  xacro origin 값으로 만듦
    (0.033, 0.0, 0.0, -math.pi / 2),
    (0.0, PHI - math.pi, math.hypot(0.026857, 0.416012), 0.0),       # offset -176.306도
    (0.0, math.pi / 2 - PHI, 0.027172, -math.pi / 2),                # offset +86.306도
    (0.362527 + 0.0602, 0.0, 0.0, math.pi / 2),
    (0.0, 0.0, 0.0, -math.pi / 2),
    (0.053, math.pi, 0.0, 0.0),
]
Q_SHIFT = np.array([0.0, -math.pi / 2, math.pi, 0.0, 0.0, 0.0])
T_BASE = np.eye(4)
T_BASE[:3, 3] = [0.027, 0.027, 0.138]                  # mani_base_link -> arm_joint1 평행이동
JOINT_NAMES = [f"arm_joint{i}" for i in range(1, 7)]
Q_LO = np.array([-1.570796, -1.570796, 0.0, -2.0, -1.7802, -1.570796])
Q_HI = np.array([1.570796, 1.570796, 3.141593, 2.0, 2.0071, 1.570796])
Q_HOME = np.clip(Q_SHIFT.copy(), Q_LO, Q_HI)           # 시작 자세 = theta 0 (접힌 자세)
BASE_FRAME = "mani_base_link"
TIP_FRAME = "gripper_base_link"


def dh_mat(d, th, a, al):
    ct, st, ca, sa = math.cos(th), math.sin(th), math.cos(al), math.sin(al)
    return np.array([[ct, -st * ca, st * sa, a * ct],
                     [st, ct * ca, -ct * sa, a * st],
                     [0.0, sa, ca, d],
                     [0.0, 0.0, 0.0, 1.0]])


def fk_frames(q):
    """URDF 관절값 q -> 프레임 {0}~{6} (mani_base_link 기준)"""
    theta = np.asarray(q) - Q_SHIFT
    frames = [T_BASE.copy()]
    for (d, off, a, al), th in zip(DH, theta):
        frames.append(frames[-1] @ dh_mat(d, th + off, a, al))
    return frames


def fk(q):
    return fk_frames(q)[-1]


def rot_log(R):
    """회전행렬 R -> 회전축*각도 벡터 (자세 오차 계산용)"""
    c = np.clip((np.trace(R) - 1.0) / 2.0, -1.0, 1.0)
    ang = math.acos(c)
    if ang < 1e-9:
        return np.zeros(3)
    v = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
    if math.pi - ang < 1e-6:  # 180도 근처
        axis = np.sqrt(np.maximum((np.diag(R) + 1.0) / 2.0, 0.0))
        axis *= np.sign(v + 1e-12)
        return axis * ang
    return v * ang / (2.0 * math.sin(ang))


def rot(axis, ang):
    c, s = math.cos(ang), math.sin(ang)
    if axis == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if axis == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


# ---------------------------------------------------------------------------
# 해석적 IK
#   DH 표에서 a4 = a5 = d5 = 0 이라 4,5,6번 축이 한 점에서 만난다 (Pieper 조건)
#   -> 수업에서 한 것처럼 앞 3축으로 손목점 위치, 뒤 3축으로 방향을 따로 푼다
#   아래 t_i 는 dh_mat 에 들어가는 각도 (theta_i + theta_offset_i)
# ---------------------------------------------------------------------------
D1, D6 = DH[0][0], DH[5][0]
L1 = DH[1][2]                              # joint2 -> joint3 길이 (a2)
L2 = math.hypot(DH[2][2], DH[3][0])        # joint3 -> 손목점 길이, a3 와 d4 를 하나로 묶음
BEND = math.atan2(DH[3][0], DH[2][2])      # link3 가 꺾인 각도 (a3 갔다가 d4)
OFFSET = np.array([row[1] for row in DH])


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def t_to_q(t):
    """DH 각도 t -> URDF 관절값 q (offset 빼고 Q_SHIFT 더함)"""
    return np.array([wrap(v) for v in np.asarray(t) - OFFSET + Q_SHIFT])


def in_limits(q):
    """관절 한계 안으로 넣어 보기 (+-2pi 도 시도). 안 들어가면 None"""
    out = []
    for i in range(6):
        for v in (q[i], q[i] - 2 * math.pi, q[i] + 2 * math.pi):
            if Q_LO[i] - 1e-6 <= v <= Q_HI[i] + 1e-6:
                out.append(min(max(v, Q_LO[i]), Q_HI[i]))
                break
        else:
            return None
    return np.array(out)


def ik_all(T_goal, q_now=Q_HOME):
    """해석적 해 전부 (최대 8개) 를 URDF 관절값으로 반환. 관절 한계는 여기서 안 봄"""
    t_now = np.asarray(q_now) - Q_SHIFT + OFFSET
    T = np.linalg.inv(T_BASE) @ T_goal     # 목표를 프레임 {0} (arm_joint1) 기준으로
    R, P = T[:3, :3], T[:3, 3]

    # 1) 손목점:  Pw = P6 - d6 * R * [0 0 1]  (손끝에서 그리퍼 z축 반대로 d6 만큼)
    xw, yw, zw = P - D6 * R[:, 2]

    sols = []
    # 2) t1: 위에서 본 손목점 방향. 앞 / 뒤로 넘기기 해서 2개
    if math.hypot(xw, yw) < 1e-6:          # 손목점이 joint1 축 위면 t1 이 안 정해짐 -> 지금 값 유지
        shoulders = [t_now[0]]
    else:
        shoulders = [math.atan2(yw, xw), math.atan2(yw, xw) + math.pi]
    for t1 in shoulders:
        # 팔 평면(프레임 {1})에서 본 손목점. alpha1 = -90도 라서 y 는 아래쪽이 +
        x = math.cos(t1) * xw + math.sin(t1) * yw
        y = D1 - zw

        # 3) t2, t3: 2링크 문제 (L1, L2), 수업 식 그대로
        c = (x * x + y * y - L1 * L1 - L2 * L2) / (2 * L1 * L2)
        if abs(c) > 1:
            continue                       # |c| > 1 이면 안 닿음 -> 해 없음
        for s in (math.sqrt(1 - c * c), -math.sqrt(1 - c * c)):   # s = +-sqrt(1-c^2) -> 팔꿈치 위 / 아래
            g = math.atan2(s, c)
            t2 = math.atan2(y, x) - math.atan2(L2 * s, L1 + L2 * c)
            t3 = g - BEND

            # 4) t4, t5, t6: 손목이 맞춰야 하는 남은 회전  R36 = R03^T * R
            T03 = np.eye(4)
            for (d, _, a, al), th in zip(DH[:3], (t1, t2, t3)):
                T03 = T03 @ dh_mat(d, th, a, al)
            R36 = T03[:3, :3].T @ R
            # DH 표대로 곱해 보면 R36 = Rz(t4) * Ry(-t5) * Rz(t6) 라서 ZYZ 오일러각으로 뽑음
            sb = math.hypot(R36[0, 2], R36[1, 2])
            if sb < 1e-6 and R36[2, 2] > 0:  # t5 = 0 (손목 특이점): t4 + t6 만 정해짐 -> t4 는 지금 값 유지
                t4 = t_now[3]
                t6 = math.atan2(R36[1, 0], R36[0, 0]) - t4
                sols.append(t_to_q([t1, t2, t3, t4, 0.0, t6]))
                continue
            for k in (1, -1):              # 손목 뒤집기 -> 2개
                b = math.atan2(k * sb, R36[2, 2])
                t4 = math.atan2(k * R36[1, 2], k * R36[0, 2])
                t6 = math.atan2(k * R36[2, 1], -k * R36[2, 0])
                sols.append(t_to_q([t1, t2, t3, t4, -b, t6]))
    return sols


def pose_err(T_goal, q):
    T = fk(q)
    return (np.linalg.norm(T_goal[:3, 3] - T[:3, 3]),
            np.linalg.norm(rot_log(T_goal[:3, :3] @ T[:3, :3].T)))


def solve_ik(T_goal, q_now):
    """해석적 IK. 관절 한계 안에 있는 해 중에서 지금 관절값과 가장 가까운 걸 고름
    (텔레옵 중에 자세가 갑자기 뒤집히지 않게). 반환: (q, ok, 위치오차, 회전오차)"""
    q_now = np.asarray(q_now, float)
    best = None
    for q in ik_all(T_goal, q_now):
        q = in_limits(q)
        if q is None:
            continue
        if best is None or np.linalg.norm(q - q_now) < np.linalg.norm(best - q_now):
            best = q
    if best is None:
        return (q_now, False, *pose_err(T_goal, q_now))
    return (best, True, *pose_err(T_goal, best))


def rpy_of(R):
    pitch = math.asin(-np.clip(R[2, 0], -1.0, 1.0))
    roll = math.atan2(R[2, 1], R[2, 2])
    yaw = math.atan2(R[1, 0], R[0, 0])
    return np.degrees([roll, pitch, yaw])


# ---------------------------------------------------------------------------
# URDF -> KDL 체인 (DH 와 상관없이 URDF 로 FK 해서 비교하려고)
# ---------------------------------------------------------------------------
def _vec(s, default="0 0 0"):
    return [float(x) for x in (s or default).split()]


def _origin(j):
    o = j.find("origin")
    if o is None:
        return kdl.Frame()
    return kdl.Frame(kdl.Rotation.RPY(*_vec(o.get("rpy"))), kdl.Vector(*_vec(o.get("xyz"))))


def kdl_chain_from_urdf(urdf_xml, base, tip):
    root = ET.fromstring(urdf_xml)
    by_child = {j.find("child").get("link"): j for j in root.findall("joint")}
    seq, link = [], tip
    while link != base:
        j = by_child[link]
        seq.append(j)
        link = j.find("parent").get("link")
    seq.reverse()
    chain = kdl.Chain()
    chain.addSegment(kdl.Segment(kdl.Joint(kdl.Joint.Fixed), _origin(seq[0])))
    names = []
    for i, j in enumerate(seq):
        nxt = _origin(seq[i + 1]) if i + 1 < len(seq) else kdl.Frame()
        if j.get("type") == "fixed":
            jt = kdl.Joint(kdl.Joint.Fixed)
        else:
            jt = kdl.Joint(j.get("name"), kdl.Vector(0, 0, 0),
                           kdl.Vector(*_vec(j.find("axis").get("xyz"), "1 0 0")), kdl.Joint.RotAxis)
            names.append(j.get("name"))
        chain.addSegment(kdl.Segment(j.get("name"), jt, nxt))
    return chain, names


class IkKeyboardTeleop(Node):
    def __init__(self, node_name="ik_keyboard_teleop"):
        super().__init__(node_name)
        self.declare_parameter("lin_step", 0.01)               # 키 한 번에 m
        self.declare_parameter("ang_step", math.radians(3.0))  # 키 한 번에 rad
        self.lin_step = self.get_parameter("lin_step").value
        self.ang_step = self.get_parameter("ang_step").value
        self.js_pub = self.create_publisher(JointState, "ik_joint_states", 10)
        self.mk_pub = self.create_publisher(MarkerArray, "ik_target_markers", 10)
        self.lock = threading.Lock()
        self.q = Q_HOME.copy()
        self.T_target = fk(self.q)
        self.version = 0          # 자세 바뀔 때마다 +1
        self.printed = -1
        self.kdl_chain = None
        self.fk_solver = None
        self.kdl_names = []
        qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(String, "robot_description", self.on_description, qos)
        self.create_timer(0.05, self.publish)
        self.create_timer(0.2, self.compare_if_changed)

    # ---- 이동 ---------------------------------------------------------------
    def apply_move(self, kind, val):
        """kind 'p': 이동 벡터 val (m) 더하기, kind 'r': 회전행렬 val 앞에 곱하기.
        IK 풀어서 성공하면 새 목표로 확정. 반환: (ok, 위치오차, 회전오차)"""
        with self.lock:
            T_new = self.T_target.copy()
            if kind == "p":
                T_new[:3, 3] += val
            else:
                T_new[:3, :3] = val @ T_new[:3, :3]
            q_new, ok, ep, er = solve_ik(T_new, self.q)
            if ok:
                self.q, self.T_target = q_new, T_new
                self.version += 1
            return ok, ep, er

    def reset(self):
        with self.lock:
            self.q = Q_HOME.copy()
            self.T_target = fk(self.q)
            self.version += 1

    # ---- FK (URDF) vs IK 목표 비교 ---------------------------------------------
    def on_description(self, msg):
        try:
            chain, names = kdl_chain_from_urdf(msg.data, BASE_FRAME, TIP_FRAME)
        except Exception as e:  # noqa: BLE001
            self.get_logger().error(f"cannot build KDL chain: {e}")
            return
        self.kdl_names = names
        self.kdl_chain = chain  # solver 가 참조만 들고 있어서 chain 을 저장해 둬야 함
        self.fk_solver = kdl.ChainFkSolverPos_recursive(self.kdl_chain)
        self.printed = -1       # URDF 받으면 한 번 출력

    def fk_urdf(self, q):
        if self.fk_solver is None:
            return None
        arr = kdl.JntArray(len(self.kdl_names))
        qmap = dict(zip(JOINT_NAMES, q))
        for i, n in enumerate(self.kdl_names):
            arr[i] = qmap.get(n, 0.0)
        f = kdl.Frame()
        self.fk_solver.JntToCart(arr, f)
        T = np.eye(4)
        for r in range(3):
            for c in range(3):
                T[r, c] = f.M[r, c]
            T[r, 3] = f.p[r]
        return T

    def compare_if_changed(self):
        if self.version != self.printed:
            self.print_compare()

    def print_compare(self, tag=""):
        with self.lock:
            q, T_t, ver = self.q.copy(), self.T_target.copy(), self.version
        T_f = self.fk_urdf(q)
        p_t, r_t = T_t[:3, 3] * 1000, rpy_of(T_t[:3, :3])
        lines = [f"---- FK vs IK {tag}".ljust(86, "-"),
                 "              x[mm]     y[mm]     z[mm]  |  roll[deg] pitch[deg]  yaw[deg]",
                 f"IK target {p_t[0]:9.3f} {p_t[1]:9.3f} {p_t[2]:9.3f}  | {r_t[0]:9.3f} {r_t[1]:9.3f} {r_t[2]:9.3f}"]
        if T_f is None:
            lines.append("FK (URDF) waiting for /robot_description ...")
        else:
            p_f, r_f = T_f[:3, 3] * 1000, rpy_of(T_f[:3, :3])
            dp = p_f - p_t
            dr = np.degrees(rot_log(T_f[:3, :3] @ T_t[:3, :3].T))
            lines += [
                f"FK (URDF) {p_f[0]:9.3f} {p_f[1]:9.3f} {p_f[2]:9.3f}  | {r_f[0]:9.3f} {r_f[1]:9.3f} {r_f[2]:9.3f}",
                f"error     {dp[0]:9.4f} {dp[1]:9.4f} {dp[2]:9.4f}  | rot about x/y/z "
                f"{dr[0]:8.4f} {dr[1]:8.4f} {dr[2]:8.4f}",
                f"          |dp| = {np.linalg.norm(dp):.4f} mm    rot err = {np.linalg.norm(dr):.4f} deg"]
        lines.append("q [deg]   [" + ", ".join(f"{math.degrees(v):7.2f}" for v in q) + "]")
        print("\n".join(lines), flush=True)
        self.printed = ver

    def report_fail(self, tag, ep, er):
        print(f"[{tag}] unreachable / joint limit (IK residual {ep*1000:.1f} mm, "
              f"{math.degrees(er):.1f} deg) -> ignored", flush=True)

    # ---- 키보드 -------------------------------------------------------------
    def on_key(self, k):
        L, A = self.lin_step, self.ang_step
        moves = {
            "a": ("p", np.array([-L, 0, 0])), "d": ("p", np.array([L, 0, 0])),
            "w": ("p", np.array([0, 0, L])), "s": ("p", np.array([0, 0, -L])),
            "q": ("p", np.array([0, L, 0])), "e": ("p", np.array([0, -L, 0])),
            "u": ("r", rot("y", A)), "j": ("r", rot("y", -A)),
            "h": ("r", rot("z", A)), "k": ("r", rot("z", -A)),
            "t": ("r", rot("x", A)), "g": ("r", rot("x", -A)),
        }
        if k == "r":
            self.reset()
            return
        if k == " ":
            self.print_compare("(pose)")
            return
        if k in "[]":
            f = 0.5 if k == "[" else 2.0
            self.lin_step *= f
            self.ang_step *= f
            print(f"step: {self.lin_step*1000:.1f} mm, {math.degrees(self.ang_step):.2f} deg", flush=True)
            return
        if k not in moves:
            return
        ok, ep, er = self.apply_move(*moves[k])
        if not ok:
            self.report_fail(k, ep, er)

    # ---- 퍼블리시 ---------------------------------------------------------
    def publish(self):
        with self.lock:
            q, T = self.q.copy(), self.T_target.copy()
        now = self.get_clock().now().to_msg()
        js = JointState()
        js.header.stamp = now
        js.name = JOINT_NAMES
        js.position = q.tolist()
        self.js_pub.publish(js)

        arr = MarkerArray()
        o = T[:3, 3]
        for i, color in enumerate([(1, 0, 0), (0, 1, 0), (0, 0, 1)]):
            m = Marker()
            m.header.frame_id = BASE_FRAME
            m.header.stamp = now
            m.ns, m.id, m.type, m.action = "ik_target", i, Marker.ARROW, Marker.ADD
            m.points = [Point(x=o[0], y=o[1], z=o[2]),
                        Point(**dict(zip("xyz", (o + 0.08 * T[:3, i]).tolist())))]
            m.scale.x, m.scale.y, m.scale.z = 0.006, 0.012, 0.02
            m.color.r, m.color.g, m.color.b = map(float, color)
            m.color.a = 0.9
            m.pose.orientation.w = 1.0
            arr.markers.append(m)
        self.mk_pub.publish(arr)


def keyboard_loop(node, stop):
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while not stop.is_set():
            r, _, _ = select.select([sys.stdin], [], [], 0.1)
            if r:
                node.on_key(sys.stdin.read(1))
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def main():
    if not sys.stdin.isatty():
        print("터미널에서 실행해야 함 (키보드 입력 필요): ros2 run arm_ik_teleop keyboard_teleop")
        return
    rclpy.init()
    node = IkKeyboardTeleop()
    print(__doc__)
    stop = threading.Event()
    th = threading.Thread(target=keyboard_loop, args=(node, stop), daemon=True)
    th.start()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        th.join(timeout=1.0)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
