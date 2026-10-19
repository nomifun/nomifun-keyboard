# 键盘状态屏幕合同

[English](screen-status.md) | 简体中文

## 画面与状态

面板为 NV3007、428×142 RGB565。画面由本地 C renderer 绘制 Nomi 眼睛、固定状态标签和四键提示：`K1 MAIN`、`K2 POLISH`、`K3 CANCEL`、`K4 TALK`。不传输用户正文、模型文本或上传资源。渲染包括呼吸、眨眼、睡眠表情，以及按键短促高亮和视线反馈。K4 高亮只表示按键事件，`listening` 必须由主机在操作系统录音就绪后显式发送。

| 协议状态 | 固定标签 | 用途 |
|---|---|---|
| connecting | LINKING | 主程序连接或尚未就绪 |
| sleeping | SLEEPY | 主程序未运行或退出 |
| ready | READY | 可接受操作 |
| starting | MIC START | 准备录音 |
| listening | LISTENING | 操作系统采集已就绪 |
| recognizing | ONE MOMENT | 收尾或普通 ASR 识别 |
| polishing | POLISHING | 正文美化 |
| error | OOPS! | 操作失败 |

## 驱动与内存

USB core 优先启动，独立低优先级屏幕 owner 初始化面板并周期刷新。生产驱动使用 `428×8×2=6848` 字节 DMA strip，按全帧窗口连续提交；RGB565 高字节先行，y 偏移 14。完整 framebuffer 只用于离线预览与 strip 一致性测试。

SPI2 使用 MOSI21 / CLK14 / CS11，DC13、RESET12，40 MHz；唯一 owner 使用 `portMAX_DELAY` 获取总线。119 条面板初始化命令来自[固定上游版本](../../SOURCE.zh.md)，先刷新初始帧，再发送 DISPON、开启背光。

背光 GPIO9 使用 LEDC 5 kHz、8 bit PWM：正常占空值 115/255，睡眠 45/255。初始化、SPI 提交或状态应用失败时将屏幕降级并关闭背光，不影响四键 USB 通信。状态应用等待渲染确认最多 500 ms。

## USB 与主机同步

```json
{"event":"nk_display","epoch":1,"request_id":2,"state":"listening"}
{"event":"nk_display_applied","epoch":1,"request_id":2,"state":"listening","applied":true,"frames":42,"backlight_on":true,"pwm_duty":115,"buffer_bytes":6848,"visual_verified":false}
```

命令使用严格 keys；epoch、request_id 与幂等规则见 [USB 合同](usb-protocol.zh.md)。回执只在完整画面 SPI 提交及背光更新成功后返回 `applied:true`。`frames` 是驱动提交计数，`visual_verified:false` 明确回执不证明实际面板朝向、色彩、亮度或排线状态；更换板卡、接线或镜像后仍需检查实物画面。

能力字段为 `display:{version:1,available:true,width:428,height:142,privacy:"status_only"}`。不可用时返回 `available:false` 与 `reason:"driver_unavailable"`。可用性变化发布同 epoch 的相邻 info/capabilities；主机只在首次握手应用 NONE，能力刷新不重置已接收按键。

主机 IPC 使用 `Control::Display{state}`，不携带正文。USB owner 同时只保留一个待确认请求，NONE 优先，待发送 display 合并为最新状态，屏幕请求不阻塞 K4 松开。错误回执、超时或驱动故障只更新 `DeviceStatus.displayAvailable/displayState/displayDetail`，不触发停止操作系统录音的通用 Failure。
