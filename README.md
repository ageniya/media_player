# media_play ROS 2 v2.0.0

独立 ROS 2 Humble 工作区，包含：

- `media_play_msgs`：`PlaybackStatus`、`VideoControl`、`VideoPlay`。
- `media_play`：视频控制、字幕显示、播放状态与网页上传服务。

语音实时字幕接口见 [VOICE_SUBTITLE_API.md](VOICE_SUBTITLE_API.md)：语音包发布 `std_msgs/msg/String` 到 `/subtitle/voice` 即可显示字幕。

## 构建

```bash
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

运行时需安装 `mpv`。本机 ROS 2 接口生成工具不能稳定处理中文路径，构建时请使用仅含英文字符的工作区路径。
