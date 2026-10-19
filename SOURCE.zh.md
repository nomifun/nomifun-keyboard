# 源码来源与许可证

[English](SOURCE.md) | 简体中文

当前固件实现四键 USB、永久 NONE 策略和固定状态屏幕。操作系统录音、模型调用、字幕与编辑由 NomiFun 原生实现；功能与模块边界见[产品设计](docs/design/nomifun-native-keyboard.zh.md)。

## 固件来源

| 内容 | 来源与使用方式 |
|---|---|
| 四键消抖、严格有界 JSON 解析 | `zerob13/vibe-keyboard` commit `019cfa099c2cb3b8d7b9aad665dbc4fd4a09096a`，按当前协议裁剪；MIT 声明见 [LICENSE](LICENSE) |
| NV3007 初始化表 | 同一 commit 的 `firmware/components/vk_board/vk_nv3007_init.inc`，保留 119 条命令；当前文件为 [nv3007_init.inc](firmware/components/nk_screen/nv3007_init.inc)，SHA256 `6c36dd6c317468a18bf59dd95fc2f828a1433f3f827dd32c492fae4d43fb385f` |
| 面板接线与数据格式 | 同一上游版本的 GPIO 定义、y=14 窗口偏移与 RGB565 字节序 |
| USB owner、屏幕 owner、Nomi 表情与字体原语 | 本地实现 |

构建使用 ESP-IDF 5.5.3 的最小依赖闭包，不链接板载音频、ESP-SR/Opus、LVGL、LED 灯条、OTA、网络或蓝牙业务。Python 仅用于 ESP-IDF、诊断和恢复工具，不参与产品运行。实际依赖与符号边界由 [validate_build.py](firmware/tools/validate_build.py) 检查。

## 私有恢复镜像的许可追溯

私有保留的历史已刷镜像使用过 ESP-SR 2.1.4、micro-opus 0.4.1 与 Opus。对应声明随镜像保存在被忽略的 `host/local/flashed-images/third-party-notices/`，用于恢复材料的许可追溯；这些组件不是当前依赖，没有源码、构建入口或产品运行路径。

原厂完整备份与已安装应用镜像按设备 MAC 私有保留，不作为产品源码或分发入口。通用恢复规范见 [DEVICE.md](DEVICE.zh.md)，具体设备、镜像哈希与路径见本地私有档案。
