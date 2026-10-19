# 贡献指南

[English](CONTRIBUTING.md) | 简体中文

## 仓库结构

| 路径 | 内容 |
| --- | --- |
| `firmware/` | ESP-IDF 5.5.3 工程：`main/` 入口与 `vk_usb`、`vk_input`、`nk_screen` 三个组件 |
| `firmware/tests/` | 使用主机编译器（`cc`）运行的离线原生 C 测试 |
| `firmware/tools/validate_build.py` | 构建后检查：配置、分区布局、镜像完整性与禁用符号 |
| `tools/` | 主机端构建脚本与诊断/预检工具（Python，依赖见 `tools/requirements.txt`） |
| `tests/` | 工具的 Python 单元测试 |
| `docs/` | 产品设计和技术合同，中英双语 |
| `DEVICE.md` / `SOURCE.md` | 硬件/恢复规则与代码来源 |

## 构建与测试

- 固件构建：`./tools/build.ps1`（Windows）或 `./tools/build.sh`（macOS/Linux/WSL）。需要 ESP-IDF 5.5.3；产物在 `firmware/build-native-screen/`，随后自动校验。
- 原生 C 测试：`cd firmware && python3 tests/run_native_tests.py`。
- Python 工具测试：在仓库根目录执行 `python -m unittest discover tests`。
- Python 工具依赖 `pip install -r tools/requirements.txt`（串口访问需要 pyserial）。

## 约定

- 每个功能只有一套实现——不保留平行/替代路径。固件仅限三个组件；不得链接音频、LVGL、LED、OTA、网络或蓝牙代码。
- 协议解析严格有界；畸形数据直接拒绝，不做猜测。
- 生成的日志、报告、截图、构建产物、`sdkconfig`、设备备份、已刷镜像和单台设备记录一律不入 Git——见 `.gitignore`。
- 未完成 [DEVICE.md](DEVICE.zh.md) 中的逐设备授权与恢复核对前，不得刷写任何设备。
- 文档中英双语：修改 `.md` 文件时，同一提交内同步更新对应的 `.zh.md` 文件（反之亦然）。
