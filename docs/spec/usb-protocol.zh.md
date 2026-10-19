# 原生四键 USB 合同

[English](usb-protocol.md) | 简体中文

当前产品仅使用键盘事件、永久 NONE 和固定状态屏幕，录音由[NomiFun OS 音频合同](input-audio.zh.md)管理。唯一产品设计见[完整设计](../design/nomifun-native-keyboard.zh.md)。当前源码固件为 `0.3-screen.2`（实物安装版本记录在本地私有设备档案，规范见 [DEVICE.md](../../DEVICE.zh.md)），必须提供 native v1、非零 epoch 与 `audio_source:system`；没有旧固件 K1 降级路径或板载音频兼容模式。

候选USB VID/PID `303A:1001` 不足以确认产品，必须检查`hardware:vibe_keyboard`、非空稳定device_id及native v1。设备ID从ROM MAC派生`NK-`加12位hex；COM、/dev/cu.*、ttyACM仅当次地址。单一Rust owner以raw/binary打开串口，不reset、不自动刷写。

帧：`01 10 length:u16-le UTF8-JSON`，host JSON≤512字节；解析 workspace 为128 token、单字符串≤128 UTF-8字节、最大深度12；当前合法命令均为flat object。原生核心只有type0x10。严格拒绝重复/额外字段、非整数ID和超界数据；有界增量解析按字节重新同步启动ROM噪音，不能允许应用日志混入协议。意外type0x01音频帧按显式协议错误报告，不解码、上传或转成OS音频。

## 握手与NONE

`transport(kind=usb) → get_device_info → device_info → nk_capabilities`，身份/能力相邻且同epoch。transport关闭旧epoch，清队列并等待在途TX结束，递增非零epoch，重置旧手势并等待所有键释放。ping每2秒，5秒租约失效后须新握手；物理连接不等于主机已就绪。

```json
{"event":"device_info","hardware":"vibe_keyboard","firmware_version":"0.3-screen.2","device_id":"NK-<12hex>","buttons":["k1","k2","k3","k4"],"native_keyboard_protocol":1,"epoch":1}
{"event":"nk_capabilities","protocol":1,"epoch":1,"firmware_build":"nomifun-native-0.3-screen.2","policy_ack":true,"wait_release":true,"audio_source":"system","key_events":["button_down","button_up","button_click"],"display":{"version":1,"available":true,"width":428,"height":142,"privacy":"status_only"}}
{"event":"nk_policy","epoch":1,"request_id":1,"voice_key":"none"}
{"event":"nk_policy_applied","epoch":1,"request_id":1,"session_id":0,"voice_key":"none","capture_stopped":true,"waiting_release":true}
```

host仅允许`voice_key:none`，不得发任何启用板载采音的策略。设备拒绝其他key、nk_stop/nk_cancel或其他业务命令。NONE回执必须匹配epoch/request，`session_id:0`、`capture_stopped:true`及`waiting_release:true`，不建立USB音频会话。

主机严格要求native v1核心`protocol/epoch/policy_ack/wait_release`与`audio_source:system`。原厂0.3.8或其他不符合合同的固件报告不受支持，不进入四键产品运行状态。固件没有任何麦克风采集入口。

request_id非零且每epoch严格递增；逐字节相同的最后request重试返回缓存，不再次重置手势；同ID不同字节为request_conflict，较小ID为stale_request，跨epoch拒绝。NONE每次新request重置手势并等释放，waiting_release:true由设备内部门禁执行，无额外ready事件。只有匹配epoch/request/voice_key:none/capture_stopped:true回执才标记策略生效，OS采集停止另行确认。

## 按键

四键均输出down/up/click，含epoch、button(k1–k4)、duration_ms，无session_id。GPIO0/18/17/16、上拉低有效，5ms采样、两次稳定。每个新epoch/NONE请求先等旧键释放；旧down/up/click不重放。host普通动作只消费click，K4只消费匹配down/up并忽略click。

按键、身份与回执进入一个有界FIFO，由唯一TX任务写完整帧。输入队列32、TX队列16，超限或250ms写入失败关闭epoch并停止准入，不伪成功。故障采用饱和单调序号，只有唯一USB owner能退休已观察的故障；并发新故障不会被清除。owner先关闭epoch、重置手势并清旧队列/解析片段，再确认TX任务退出与IDF `usb_serial_jtag_wait_tx_done` 的驱动缓冲排空证明，最后有界排空旧RX至明确空闲；仍忙、读取失败、未排空或计数耗尽时保持故障。退休后epoch仍为0，只接受后续完整新transport；新epoch还须显式NONE及全键释放，不能自动恢复按键准入。主机每次重开串口先清接收缓冲并创建新Parser，避免已到达主机的旧帧残片进入新连接。生产console/log/panic文本禁用。硬件动作不包含模型文本或可执行命令。

实体k1–k4固定执行K1–K4，不提供校准或映射缓存。主程序未运行时，服务只接受k1冷启动，3秒内连按合并；app ready后交给主程序窗口操作。IPC只允许typed NONE、Rearm、Display、DesktopStopped、Heartbeat和管理Shutdown，有鉴权、独占owner和有界消息。

`Rearm{generation>0}`是主机IPC恢复屏障，不增加设备USB命令：复用新request的NONE，等匹配实际回执且该轮后续NONE队列清空后，在与按键相同FIFO中发送`Rearmed{generation}`。只有最新generation可证明；重复请求不重置设备，旧generation忽略。主程序在连接、恢复及总开关/K4/录音配置变更时先撤销本地armed；只切换K2或K3不重置活动K4手势。上述恢复场景中的旧Status(applied)不能重新准入；只接受本轮Rearmed。设备重连仅保留主机generation，不保留旧连接的完成证明；固件仍负责旧按压释放门禁。

普通GUI退出确认OS流停止并发DesktopStopped，daemon保留NONE/K1。外部停止/卸载先通过独立`desktop.json`鉴权端点确认OS停采，再等待`desktop.lock`生命锁释放；缺descriptor但锁busy是错误，不能当GUI不存在。CLI持独占生命锁直至daemon最终完成回执与登录清理结束。daemon最终成功同时要求NONE确认及GUI的DesktopStopped，断连不能冒充OS停采证明。

若GUI已经崩溃退出，其OS音频流随进程结束，但daemon仍保留unproven；CLI获得生命锁后可用typed `request_shutdown_after_desktop_exit(&DesktopQuiescence)`传递独立退出证明。该guard持有`desktop.lock`及专属`desktop-exited.lock`，期间保存私有随机`desktop-exited.json`；服务端核对随机值与两把锁仍被持有后才允许回收孤儿daemon。guard结束先删除证明再释放维护锁和GUI生命锁；CLI被杀后即使文件残留，维护锁free也不接受。新GUI只持GUI生命锁并先清旧证明，因此它刚启动尚未删文件的窗口也不能复用旧proof。应用内退出仍使用DesktopStopped原路径，不能自称进程已退出。

公开合成fixture：[native-keyboard-v1.json](fixtures/native-keyboard-v1.json)。当前C测试覆盖四键完整事件、无session、旧键释放、NONE幂等、拒绝启用采音、epoch与JSON边界；真实设备与源码版本分别记录，不把离线构建标为刷写成功。

## 本期状态屏幕扩展

状态屏幕合同见[screen-status.md](screen-status.zh.md)。cap增加display block，nk_display及nk_display_applied与NONE共用epoch/request队列；仅固定状态字符串，不传正文。实际TX队列减为16项，USB优先初始化，屏幕不可用独立降级。能力更新不会重新应用NONE或丢弃活动K4 up。
