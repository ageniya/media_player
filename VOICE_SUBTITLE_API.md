# 语音实时字幕接口

语音播报或 ASR 功能包不需要依赖 `media_play_msgs`。当需要在机器人屏幕显示实时字幕时，发布标准 ROS 2 消息到以下话题：

```text
Topic: /subtitle/voice
Type:  std_msgs/msg/String
QoS:   默认可靠 QoS，队列深度 10
```

`data` 是当前需要显示的完整字幕文本。每条新消息都会替换当前屏幕字幕；发布空字符串会清空字幕。

## 命令行验证

```bash
ros2 topic pub --once /subtitle/voice std_msgs/msg/String "{data: '您好，正在为您播报'}"
ros2 topic pub --once /subtitle/voice std_msgs/msg/String "{data: ''}"
```

## Python 发布示例

```python
from std_msgs.msg import String

subtitle_pub = self.create_publisher(String, '/subtitle/voice', 10)
subtitle_pub.publish(String(data='第一句实时字幕'))
```

## 使用约定

- 对增量语音识别，请每次发布“当前完整句子”，不要只发布新增的几个字。
- 播报结束后，语音包可发布空字符串清屏。
- `media_play` 默认将每条语音字幕显示 2000 ms；语音包持续发布时会自动续显。可在启动视频节点时设置参数 `voice_subtitle_duration_ms` 调整显示时间。
