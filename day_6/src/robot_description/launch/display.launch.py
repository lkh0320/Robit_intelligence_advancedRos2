from launch import LaunchDescription
from launch.substitutions import (
    Command,
    FindExecutable,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    urdf_file = Command(
        [
            PathJoinSubstitution([FindExecutable(name="xacro")]),
            " ",
            PathJoinSubstitution(
                [FindPackageShare("robot_description"), "urdf", "eclipse.xacro"]
            ),
        ]
    )
    robot_description = ParameterValue(urdf_file, value_type=str)
    rviz_config_file = PathJoinSubstitution(
        [FindPackageShare("robot_description"), "config", "eclipse.rviz"]
    )

    return LaunchDescription(
        [
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                parameters=[{"robot_description": robot_description}],
                output="screen",
            ),
            Node(
                package="joint_state_publisher_gui",
                executable="joint_state_publisher_gui",
                # arm_ik_teleop 이 보내는 팔 관절값 합치기 (안 띄우면 슬라이더 그대로 사용)
                parameters=[{"source_list": ["/ik_joint_states"]}],
                output="screen",
            ),
            Node(
                package="rviz2",
                executable="rviz2",
                arguments=["-d", rviz_config_file],
                output="screen",
            ),
        ]
    )
