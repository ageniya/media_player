from glob import glob
from setuptools import setup

package_name = 'media_play'

setup(
    name=package_name,
    version='2.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='wangyulong',
    maintainer_email='yl.wang@zj-humanoid.com',
    description='ROS 2 media playback package',
    license='MIT',
    entry_points={
        'console_scripts': [
            'video_player = media_play.video_player:main',
            'web_upload = media_play.web_upload:main',
        ],
    },
)
