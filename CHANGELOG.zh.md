# 更新日志

[English](CHANGELOG.md) | 简体中文

## 0.3-screen.2 — 2026-10-19

首个公开发布版本。

- ESP32-S3 四键 USB 键盘固件：k1–k4 → K1–K4 固定映射，5 ms 消抖，输出带 epoch 与时长的 down/up/click 事件。
- native v1 串口协议：`transport`/`get_device_info`/`ping` 握手，非零 epoch 与 5 秒租约，`request_id` 严格递增且重复请求幂等，严格有界 JSON（输入 512 字节、128 token、128 字节字符串、深度 12）。
- 永久 `voice_key:none` 策略：无板载音频路径、无音频帧，旧业务命令按显式协议错误拒绝。
- `nk_display`/`nk_display_applied` 固定状态屏幕：NV3007 428×142 RGB565，SPI2 + 6848 字节 DMA strip，8 种固定状态、Nomi 表情、按键反馈、LEDC PWM 背光，失败独立降级。
- 离线工具链：五个原生 C 测试程序、`validate_build.py` 镜像检查、`device_probe.py`/`native_diagnostic.py` 只读诊断、`inspect_flash.py`/`native_preflight.py` 恢复核对。
