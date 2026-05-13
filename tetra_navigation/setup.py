from setuptools import find_packages, setup

package_name = 'tetra_navigation'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
	    ('share/ament_index/resource_index/packages',
		['resource/tetra_navigation']),
	    ('share/tetra_navigation', ['package.xml']),
	    ('share/tetra_navigation/launch', ['launch/waypoint_follower_launch.py']),
	],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ayaori',
    maintainer_email='donghee030393@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'waypoint_sender = tetra_navigation.waypoint_sender:main',
            'waypoint_stop = tetra_navigation.waypoint_stop:main',
            'apriltag_visualizer = tetra_navigation.apriltag_visualizer:main',
            'apriltag_servo = tetra_navigation.apriltag_servo:main',
        ],
    },
)
