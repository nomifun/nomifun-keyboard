# 四键与状态屏幕固件

[English](README.md) | 简体中文

唯一固件入口为 `main/app_main.c`，当前源码版本 `0.3-screen.2`，仅包含 `vk_usb`、`vk_input`、`nk_screen`。设备始终为 NONE，只传四键事件和固定屏幕状态，K3 显示 `CANCEL`；OS 麦克风、ASR、字幕与编辑属于 NomiFun。USB 先启动，屏幕使用独立低优先级 owner 和 6848 字节 DMA strip，屏幕失败独立降级。实物已安装版本记录在本地私有设备档案，离线构建不代表已刷写。

传输或队列故障关闭当前 epoch，唯一 USB owner 确认 TX 任务及驱动发送缓冲均已排空、清除旧命令和手势后回到等待新握手。驱动仍忙或未确认清净时保持故障；恢复仍须新 transport、NONE 与全键释放，不重放旧按压。

没有 I2S/AFE/Opus、ESP-SR、LVGL/资源上传、LED 灯条、Agent、OTA 或网络业务。JSON 仅保留当前命令使用的接口，限制为 512 字节输入、128 token、128 字节字符串；完整校验和拒绝异常数据保留。三组件结构见[固件合同](../docs/spec/firmware.zh.md)，USB 与屏幕字段见[USB 合同](../docs/spec/usb-protocol.zh.md)、[状态屏幕合同](../docs/spec/screen-status.zh.md)。

## 构建与离线验证

在工程根目录执行 `./tools/build.ps1`（Windows）或 `./tools/build.sh`（macOS/Linux/WSL），使用 ESP-IDF 5.5.3，输出 `firmware/build-native-screen/vibe_keyboard.bin`，随后自动执行 `firmware/tools/validate_build.py`。检查生产日志/console 禁用、16 MiB Flash、实际 `ota_0` 布局、镜像大小和校验，以及不允许的业务符号未链接。生成目录与 sdkconfig 为本机缓存，不属于源码或分发入口。

在 `firmware` 目录执行 `python3 tests/run_native_tests.py`（需要 `cc`；Windows 使用 WSL）。五个 C 程序及 panel 失败场景覆盖四键/NONE 与最终能力字段、epoch/释放/幂等、严格 JSON 边界与 u32、消抖、119 条面板初始化/窗口/字节序/背光、strip 与完整 framebuffer 逐像素一致及失败/超时关灯。需要预览时给测试脚本附显式输出目录，再由 `tools/render_screen_preview.py` 转成 PNG；完整 framebuffer 只在离线测试使用。

## 镜像与恢复

构建产物属于当前源码的离线输出，不表示实物已经更新。硬件规格、分区与恢复规则见[设备说明](../DEVICE.zh.md)；实际身份、已安装镜像和原厂备份映射记录在维护者被忽略的 `host/local/device-recovery-record.zh.md`。原厂完整备份在工程外按 MAC 保存，已刷应用副本与对应许可位于 `host/local/flashed-images/`，不得作为产品分发入口。

刷写必须针对具体镜像另行核对授权、分区和恢复路径，不执行 IDF 自动打印的全量 flash 命令，不改 bootloader、分区表、NVS、OTA 元数据、storage 或 eFuse。已刷历史镜像与许可证仅为私有硬件追溯材料，不保存对应取消源码或第二产品运行路径。
