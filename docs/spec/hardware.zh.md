# 硬件合同

[English](hardware.md) | 简体中文

目标板为 ESP32-S3、16 MiB Flash、8 MiB PSRAM。设备身份、照片、接线、分区和原厂备份映射统一见 [DEVICE.md](../../DEVICE.zh.md)。USB VID/PID `303A:1001` 只用于发现候选设备，连接后必须校验 native v1 协议与稳定 ID；串口名不是设备身份。

四键使用 GPIO0/18/17/16，上拉、低电平按下。NV3007 面板为 428×142 RGB565，MOSI21、CLK14、CS11、DC13、RESET12，背光 GPIO9。固件只初始化四键、USB 和状态屏幕；产品录音来自操作系统麦克风，不初始化板载音频、灯条或无线链路。

屏幕仅显示固定状态、Nomi 表情与四键提示，不接收用户字幕。驱动、背光与主机状态同步见[屏幕合同](screen-status.zh.md)。

原厂完整 Flash、设备私有数据和已刷镜像不进入 Git 或产品包。刷写须核对当前设备 MAC、实际分区、镜像 descriptor/hash 与对应原厂备份，并取得具体写入范围的授权；普通应用更新不修改 bootloader、分区表、NVS、OTA 元数据、storage 或 eFuse。完整恢复使用同一 MAC 的原厂备份，禁止混用设备备份。
