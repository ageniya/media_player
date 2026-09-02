from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    video_dir = LaunchConfiguration('video_dir')
    return LaunchDescription([
        DeclareLaunchArgument('video_dir', default_value='~/media_play/videos'),
        Node(package='media_play', executable='video_player', name='video_player',
             parameters=[{'video_dir': video_dir}], output='screen'),
        Node(package='media_play', executable='web_upload', name='media_upload_server', output='screen'),
    ])
