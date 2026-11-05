"""미니 과제: turtlesim + broadcaster 2개 + follower (+ rotator) 를 한 번에 실행.

launch 인자
  params_file   : follower 파라미터 YAML (기본: config/follow_params.yaml)
  use_rotator   : true 면 rotator 로 turtle1 을 rotator_theta 만큼 돌린다
  rotator_theta : rotator 목표 각도 [rad]

예) ros2 launch turtle_mini follow.launch.py \
      params_file:=$(ros2 pkg prefix --share turtle_mini)/config/follow_fast.yaml use_rotator:=true
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, TimerAction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    default_params = os.path.join(
        get_package_share_directory('turtle_mini'), 'config', 'follow_params.yaml')

    params_file = LaunchConfiguration('params_file')
    use_rotator = LaunchConfiguration('use_rotator')
    rotator_theta = LaunchConfiguration('rotator_theta')

    return LaunchDescription([
        DeclareLaunchArgument('params_file', default_value=default_params,
                              description='turtle_follower 파라미터 YAML'),
        DeclareLaunchArgument('use_rotator', default_value='false',
                              description='rotator 액션 클라이언트 실행 여부'),
        DeclareLaunchArgument('rotator_theta', default_value='3.14',
                              description='rotator 목표 각도 [rad]'),

        Node(package='turtlesim', executable='turtlesim_node', name='sim'),
        Node(
            package='turtle_mini', executable='pose_broadcaster',
            name='broadcaster1', parameters=[{'turtlename': 'turtle1'}],
        ),
        Node(
            package='turtle_mini', executable='pose_broadcaster',
            name='broadcaster2', parameters=[{'turtlename': 'turtle2'}],
        ),
        Node(
            package='turtle_mini', executable='turtle_follower',
            name='turtle_follower', parameters=[params_file],
        ),
        # turtle2 가 따라오기 시작한 뒤에 turtle1 을 돌리도록 3초 뒤 실행
        TimerAction(period=3.0, actions=[
            Node(
                package='turtle_mini', executable='rotator', name='rotator',
                # rotator_theta:=2 처럼 정수로 줘도 float 로 넘긴다
                parameters=[{'theta': ParameterValue(rotator_theta, value_type=float),
                             'turtle_name': 'turtle1'}],
                condition=IfCondition(use_rotator),
            ),
        ]),
    ])
