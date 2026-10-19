# NomiFun 原生四键字幕板

[English](README.md) | 简体中文

用四键键盘控制 NomiFun：按住 K4 录入系统麦克风语音，K2 美化全文，K3 取消当次未完成操作，K1 显示或隐藏主窗口。ASR 支持实时流式与云端普通识别。透明字幕可手动编辑，在光标位置插入或替换选区，同稿连续续写，支持字号调整和字形美化光晕。

键盘只提供四键与固定状态屏幕，板载采音永久 NONE。固件由 USB、消抖和必要的 NV3007/SPI/背光组件组成；录音、ASR、字幕与设置由 NomiFun Rust/Tauri 原生管理。

## 使用

四键职责固定，连接后即可使用。在 NomiFun「设置 → 拓展键盘」选择系统麦克风、ASR 模式/模型与文本模型。按住 K4 后，等待青绿色聆听提示再说话；松开完成本段。需要放弃本段或美化时按 K3，保留此前已定稿正文。可以继续录入或编辑，按 K2 美化。焦点在字幕内时，用系统 Ctrl+C / Command+C 复制所选文字，再由用户在目标应用自行粘贴。Esc 关闭并清空本轮；输入法组合中的 Esc 先交给输入法。下一次录音创建新文档。

## 开发入口

| 位置 | 用途 |
| --- | --- |
| `firmware/components/vk_usb/` | USB 四键、NONE/Display、epoch/租约与释放门禁 |
| `firmware/components/vk_input/` | 四键消抖 |
| `firmware/components/nk_screen/` | 状态屏幕与条带渲染 |
| `tools/build.ps1`、`tools/build.sh` | ESP-IDF 构建与离线镜像检查 |
| `tools/device_probe.py`、`tools/native_diagnostic.py` | 设备身份、NONE、按键和屏幕诊断 |
| `tools/inspect_flash.py`、`tools/native_preflight.py` | 原厂镜像检查与刷写预检 |

完整行为见[产品设计](docs/design/nomifun-native-keyboard.zh.md)，接口见[文档索引](docs/README.zh.md)，构建与刷写见[固件说明](firmware/README.zh.md)，硬件和原厂恢复见[设备档案](DEVICE.zh.md)，代码来源见[SOURCE](SOURCE.zh.md)。日志、报告、截图和私有恢复材料不进入 Git 或产品分发。
