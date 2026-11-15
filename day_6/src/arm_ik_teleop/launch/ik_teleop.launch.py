"""IK 텔레옵 GUI 만 띄움. RViz 는 먼저 따로 띄우기:

    ros2 launch robot_description display.launch.py
    ros2 launch arm_ik_teleop ik_teleop.launch.py   # 이 파일

GUI 가 /ik_joint_states 로 팔 관절값을 보내면 display.launch.py 의
joint_state_publisher_gui 가 source_list 로 합쳐서 보여준다.
FK(URDF) vs IK 비교는 이 터미널에 출력된다.
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument("lin_speed", default_value="50.0", description="버튼 누르고 있을 때 이동 속도 mm/s"),
            DeclareLaunchArgument("ang_speed", default_value="20.0", description="버튼 누르고 있을 때 회전 속도 deg/s"),
            Node(
                package="arm_ik_teleop",
                executable="teleop_gui",
                output="screen",
                emulate_tty=True,
                parameters=[{
                    "lin_speed": LaunchConfiguration("lin_speed"),
                    "ang_speed": LaunchConfiguration("ang_speed"),
                }],
            ),
        ]
    )
