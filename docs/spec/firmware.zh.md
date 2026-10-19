# 最终固件结构

[English](firmware.md) | 简体中文

固件只有 `vk_usb`、`vk_input`、`nk_screen` 三个组件。`app_main` 先启动 USB，再初始化屏幕；没有替代运行入口或业务插件。

`vk_usb` 的唯一 TX owner 用 16 项 FIFO 交付完整 JSON 帧。输入 scanner 每 5 ms 消抖，进入 32 项队列；协议 owner 处理身份、NONE、Display、按键、epoch 与 5 秒租约。新握手和新 NONE 等待旧键释放，Display 不重置手势。设备无录音线程、音频数据或模型凭据。

JSON 主机输入最多 512 字节，workspace 为 128 token、字符串最多 128 UTF-8 字节、深度最多 12；命令只需要 flat object。仍验证完整 JSON、重复键、UTF-8、整数范围、额外字段与边界；只导出实际使用的读取接口，不保留旧资源业务的通用遍历、布尔、signed/64-bit getter。

`nk_screen` 独占 SPI2，保留固定 119 条 NV3007 初始化表和本地字形/图形。428×142 的实际 frame 以 428×8 strip 提交，DMA 缓冲仅 6848 字节。固定状态、Nomi 呼吸/眨眼与按键反馈不包含用户正文；录音状态由主机真实状态决定。驱动失败/超时关背光并独立降级，不能阻断四键或冒充 OS 停采证明。

ESP-IDF 最小依赖闭包不链接 I2S/AFE、ESP-SR/Opus、LVGL、资源上传、LED 灯条、OTA 或网络/蓝牙业务。NomiFun 设备服务单独持有串口，字幕、系统录音、ASR、编辑、配置和安装归主程序；完整合同见[USB](usb-protocol.zh.md)、[OS 音频](input-audio.zh.md)、[状态屏幕](screen-status.zh.md)。构建、离线测试及保护实物的规则见[固件入口](../../firmware/README.zh.md)。
