from glob import glob

from setuptools import find_packages, setup

package_name = "arm_ik_teleop"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="lkh",
    maintainer_email="lkh060320@gmail.com",
    description="Eclipse arm end-effector IK teleop (GUI / keyboard) with FK(URDF) vs IK comparison",
    license="TODO",
    entry_points={
        "console_scripts": [
            "teleop_gui = arm_ik_teleop.teleop_gui:main",
            "keyboard_teleop = arm_ik_teleop.ik_core:main",
        ],
    },
)
