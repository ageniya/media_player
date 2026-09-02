#!/usr/bin/env python3
"""ROS 2 Humble video player backed by mpv JSON IPC."""

import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.node import Node
from std_msgs.msg import String

from media_play_msgs.action import VideoPlay
from media_play_msgs.msg import PlaybackStatus
from media_play_msgs.srv import VideoControl


VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.mov', '.avi', '.webm'}


class MpvPlayer:
    def __init__(self):
        self.process = None
        self.socket_path = f'/tmp/media_play_mpv_{os.getuid()}.sock'
        self.current_video = ''
        self.loop = False
        self.volume = 50
        self.lock = threading.RLock()

    def _command(self, command, timeout=1.0):
        if not self.process or self.process.poll() is not None or not os.path.exists(self.socket_path):
            return False, None
        request = json.dumps({'command': command}).encode() + b'\n'
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(timeout)
                client.connect(self.socket_path)
                client.sendall(request)
                reply = client.recv(65536)
            data = json.loads(reply.decode().splitlines()[0])
            return data.get('error') == 'success', data.get('data')
        except (OSError, ValueError, json.JSONDecodeError):
            return False, None

    def _property(self, name, default=None):
        ok, value = self._command(['get_property', name])
        return value if ok else default

    def play(self, path, loop=False):
        with self.lock:
            self.stop()
            try:
                os.unlink(self.socket_path)
            except FileNotFoundError:
                pass
            args = ['mpv', '--force-window=yes', '--really-quiet',
                    f'--input-ipc-server={self.socket_path}', f'--volume={self.volume}']
            if loop:
                args.append('--loop-file=inf')
            args.append(path)
            try:
                self.process = subprocess.Popen(args)
            except FileNotFoundError:
                return False, 'mpv 未安装'
            for _ in range(50):
                if os.path.exists(self.socket_path):
                    self.current_video, self.loop = path, loop
                    return True, '开始播放'
                if self.process.poll() is not None:
                    return False, 'mpv 启动失败'
                time.sleep(0.1)
            return False, '等待 mpv IPC 超时'

    def pause(self):
        return self._set_property('pause', True, '已暂停')

    def resume(self):
        return self._set_property('pause', False, '已恢复')

    def seek(self, position):
        ok, _ = self._command(['set_property', 'time-pos', float(position)])
        return ok, '已跳转' if ok else '跳转失败'

    def set_volume(self, volume):
        self.volume = max(0, min(100, int(volume)))
        ok, _ = self._command(['set_property', 'volume', self.volume])
        return (True, '音量已设置') if ok or not self.process else (False, '设置音量失败')

    def _set_property(self, name, value, message):
        ok, _ = self._command(['set_property', name, value])
        return ok, message if ok else f'{message}失败'

    def show_text(self, text, duration_ms=5000):
        self._command(['show-text', str(text), int(duration_ms)])

    def stop(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                self._command(['quit'])
                try:
                    self.process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    self.process.terminate()
            self.process = None
            self.current_video = ''
            self.loop = False
            return True, '已停止'

    def status(self):
        if not self.process or self.process.poll() is not None:
            return {'status': 'stopped', 'position': 0.0, 'duration': 0.0,
                    'current_video': '', 'loop': False, 'volume': self.volume}
        paused = bool(self._property('pause', False))
        eof = bool(self._property('eof-reached', False))
        return {
            'status': 'finished' if eof else ('paused' if paused else 'playing'),
            'position': float(self._property('time-pos', 0.0) or 0.0),
            'duration': float(self._property('duration', 0.0) or 0.0),
            'current_video': os.path.basename(self.current_video),
            'loop': self.loop,
            'volume': self.volume,
        }


class VideoPlayer(Node):
    def __init__(self):
        super().__init__('video_player')
        default_dir = os.path.expanduser('~/media_play/videos')
        self.declare_parameter('video_dir', default_dir)
        self.declare_parameter('default_expression', '1-default.mp4')
        self.declare_parameter('status_rate', 2.0)
        self.declare_parameter('voice_subtitle_duration_ms', 2000)
        self.video_dir = Path(self.get_parameter('video_dir').value).expanduser()
        self.video_dir.mkdir(parents=True, exist_ok=True)
        self.default_expression = self.get_parameter('default_expression').value
        self.player = MpvPlayer()
        self.voice_subtitle_duration_ms = int(self.get_parameter('voice_subtitle_duration_ms').value)
        self.videos = {}
        self._scan_videos()
        self.subtitle_visible = False
        self.service = self.create_service(VideoControl, 'control', self.on_control)
        self.status_pub = self.create_publisher(PlaybackStatus, 'status', 10)
        self.create_subscription(String, '/subtitle/customer', self.on_customer_subtitle, 10)
        self.create_subscription(String, '/subtitle/robot', self.on_robot_subtitle, 10)
        # Public integration point for a speech / ASR package.  The newest
        # String replaces the text currently shown on the robot screen.
        self.create_subscription(String, '/subtitle/voice', self.on_voice_subtitle, 10)
        rate = max(float(self.get_parameter('status_rate').value), 0.1)
        self.create_timer(1.0 / rate, self.publish_status)
        self.action = ActionServer(self, VideoPlay, 'play', self.execute_action,
                                   goal_callback=lambda _: GoalResponse.ACCEPT,
                                   cancel_callback=lambda _: CancelResponse.ACCEPT)
        self.get_logger().info(f'video directory: {self.video_dir}')

    def _scan_videos(self):
        self.videos = {entry.name: str(entry) for entry in self.video_dir.iterdir()
                       if entry.is_file() and entry.suffix.lower() in VIDEO_EXTENSIONS}

    def resolve_video(self, value):
        if not value:
            return None
        candidate = Path(value).expanduser()
        if candidate.is_absolute() and candidate.is_file():
            return str(candidate)
        if value in self.videos:
            return self.videos[value]
        normalized = value.lower().strip()
        for name, path in self.videos.items():
            stem = Path(name).stem.lower()
            if normalized in (stem, stem.split('-', 1)[-1]):
                return path
        return None

    def fill_response(self, response, success, message):
        status = self.player.status()
        response.success = success
        response.message = message
        response.current_video = status['current_video']
        response.status = status['status']
        return response

    def on_control(self, request, response):
        command = request.command.lower().strip()
        if command in ('play', 'switch'):
            path = self.resolve_video(request.video_path)
            if not path:
                return self.fill_response(response, False, f'视频未找到: {request.video_path}')
            ok, message = self.player.play(path, request.loop)
        elif command == 'pause':
            ok, message = self.player.pause()
        elif command == 'resume':
            ok, message = self.player.resume()
        elif command == 'stop':
            ok, message = self.player.stop()
            self.subtitle_visible = False
        elif command == 'seek':
            ok, message = self.player.seek(request.position)
        elif command == 'volume':
            ok, message = self.player.set_volume(request.volume)
        elif command == 'list':
            ok, message = True, '|'.join(sorted(self.videos))
        elif command == 'refresh':
            self._scan_videos()
            ok, message = True, f'已刷新，共 {len(self.videos)} 个条目'
        else:
            ok, message = False, f'未知命令: {command}'
        return self.fill_response(response, ok, message)

    def publish_status(self):
        data = self.player.status()
        message = PlaybackStatus()
        message.current_video = data['current_video']
        message.status = data['status']
        message.position = data['position']
        message.duration = data['duration']
        message.loop = data['loop']
        message.volume = data['volume']
        self.status_pub.publish(message)

    def on_customer_subtitle(self, message):
        self.player.show_text(message.data)
        self.subtitle_visible = bool(message.data)

    def on_robot_subtitle(self, message):
        self.player.show_text(message.data)
        self.subtitle_visible = bool(message.data)

    def on_voice_subtitle(self, message):
        """Display incremental speech-recognition text; an empty value clears it."""
        self.player.show_text(message.data, self.voice_subtitle_duration_ms)
        self.subtitle_visible = bool(message.data)

    def execute_action(self, goal_handle):
        goal = goal_handle.request
        command = goal.command.lower().strip()
        if command in ('pause', 'resume', 'stop'):
            ok, message = {'pause': self.player.pause, 'resume': self.player.resume,
                           'stop': self.player.stop}[command]()
            result = VideoPlay.Result()
            result.success, result.cancelled, result.message = ok, False, message
            result.final_expression = ''
            goal_handle.succeed() if ok else goal_handle.abort()
            return result
        path = self.resolve_video(goal.video_path) or self.resolve_video(goal.expression_name)
        result = VideoPlay.Result()
        if not path:
            result.success, result.cancelled = False, False
            result.message = f'视频未找到: {goal.video_path or goal.expression_name}'
            result.final_expression = ''
            goal_handle.abort()
            return result
        ok, message = self.player.play(path, goal.loop)
        if not ok:
            result.success, result.cancelled, result.message, result.final_expression = False, False, message, ''
            goal_handle.abort()
            return result
        if goal.subtitle_text:
            self.player.show_text(goal.subtitle_text)
            self.subtitle_visible = True
        started = time.monotonic()
        while rclpy.ok():
            if goal_handle.is_cancel_requested:
                self.player.stop()
                result.success, result.cancelled, result.message = False, True, '目标已取消'
                result.final_expression = ''
                goal_handle.canceled()
                return result
            state = self.player.status()
            feedback = VideoPlay.Feedback()
            feedback.current_video = state['current_video']
            feedback.status = state['status']
            feedback.position = state['position']
            feedback.duration = state['duration']
            elapsed = time.monotonic() - started
            denominator = goal.max_duration if goal.max_duration > 0 else state['duration']
            feedback.progress = min(1.0, elapsed / denominator) if denominator else 0.0
            feedback.subtitle_visible = self.subtitle_visible
            goal_handle.publish_feedback(feedback)
            if not goal.loop and state['status'] in ('finished', 'stopped'):
                break
            if goal.max_duration > 0 and elapsed >= goal.max_duration:
                self.player.stop()
                break
            time.sleep(0.2)
        final = ''
        if goal.restore_default:
            default = self.resolve_video(goal.default_expression) or self.resolve_video(self.default_expression)
            if default:
                self.player.play(default, True)
                final = os.path.basename(default)
        self.subtitle_visible = False
        result.success, result.cancelled, result.message, result.final_expression = True, False, '播放完成', final
        goal_handle.succeed()
        return result


def main():
    rclpy.init()
    node = VideoPlayer()
    try:
        rclpy.spin(node)
    finally:
        node.player.stop()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
