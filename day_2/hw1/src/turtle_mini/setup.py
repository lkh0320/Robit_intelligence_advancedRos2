from glob import glob

from setuptools import find_packages, setup

package_name = 'turtle_mini'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='lkh0320',
    maintainer_email='lkh060320@gmail.com',
    description='Day 2 미니 과제: TF2 + Launch + Action (turtlesim)',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'pose_broadcaster = turtle_mini.pose_broadcaster:main',
            'turtle_follower = turtle_mini.turtle_follower:main',
            'rotator = turtle_mini.rotator:main',
        ],
    },
)
