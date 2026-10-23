# SoundGate终端与平台MQTT通信协议

版本：1.1
日期：2026年10月23日
适用对象：单片机固件、4G通信模块、OneNET平台适配、SoundGate后端和联调测试人员

## 1 文档目的

本协议定义SoundGate终端通过4G模块接入中国移动OneNET后的应用层通信规则，覆盖设备上线、属性上报、属性读取、参数设置、命令应答、异常处理和WAV文件分片传输。终端主控资源有限，所有终端收发的MQTT Payload必须采用UTF-8紧凑JSON，单帧总长度不得超过200字节。长度按实际UTF-8字节数计算，不按字符数计算。

根据2026年9月23日和10月5日的OneNET调试截图，现有OneJSON属性已出现成功写入、主动获取和返回真实值的联调证据：9月23日`DftVolume=6`写入后读取返回6；10月5日全部12个物模型字段多次整组读取成功，并有整组写入与单字段写入成功记录。本版本把六个仍使用的工作参数列为“已联调验证”，把`Period`、`RushTime`和`WalkTime`列为已验证但业务弃用的兼容字段。文件传输已完成服务端WAV复验与分片规划，实际自定义Topic、ACK状态机和Flash切换仍须联合调试，不能把服务端接收文件视为终端更新成功。

## 2 系统角色

- 终端：单片机主控和4G通信模块，解析OneJSON命令，执行控制并上报状态。
- OneNET：负责MQTT连接、设备鉴权、消息路由、在线状态和物模型管理。
- SoundGate后端：通过OneNET应用接口设置或主动读取属性，保存账号、设备和音量计划。
- SoundGate前端：发起业务操作并显示终端主动读取或主动上报的真实值。

## 3 基本通信约束

| 项目 | 规范 |
|---|---|
| 协议 | MQTT 3.1.1，OneNET OneJSON物模型 |
| 编码 | UTF-8 |
| 应用载荷 | 紧凑JSON，不允许空格、注释、换行和无用字段 |
| 单帧上限 | 200字节，包含完整MQTT Payload |
| QoS | 控制、读取、文件帧使用QoS 1；周期状态上报可使用QoS 0或1 |
| 保活 | 建议60秒，断线后指数退避重连，最大退避60秒 |
| 消息ID | 十进制字符串，1至13位；同一连接周期内不得重复使用未完成ID |
| 超时 | 普通属性命令5秒；平台业务层最多等待30秒并允许轮询 |
| 重试 | 相同消息ID最多重试3次；终端必须按消息ID实现幂等 |
| 数值 | 全部使用JSON数字，不得用带单位字符串代替 |
| 时间 | 终端只保存和运行标准UTC；平台按设备IANA时区及当日DST规则把当地时间转换为UTC后下发 |

终端在组包前必须使用snprintf计算并检查长度。解析后必须校验字段类型、范围和业务关系，校验失败不得修改运行参数。

## 4 OneNET Topic映射

以下Topic中的pid为产品ID，device为OneNET设备名。

| 功能 | 下行Topic | 上行Topic |
|---|---|---|
| 属性设置 | `$sys/{pid}/{device}/thing/property/set` | `$sys/{pid}/{device}/thing/property/set_reply` |
| 属性获取 | `$sys/{pid}/{device}/thing/property/get` | `$sys/{pid}/{device}/thing/property/get_reply` |
| 属性上报 | － | `$sys/{pid}/{device}/thing/property/post` |
| 上报应答 | `$sys/{pid}/{device}/thing/property/post/reply` | － |
| 生命周期 | 由OneNET维护 | 平台向应用侧发布上线和离线事件 |

Topic最终以产品当前OneJSON接入配置为准。终端不得把平台AccessKey、用户Token或产品密钥放入Payload。

## 5 通用报文结构

### 5.1 属性设置

平台下发：

```json
{"id":"101","version":"1.0","params":{"DftVolume":5}}
```

终端处理顺序：校验JSON、校验ID、校验字段、校验范围、写入运行参数、按需要写入非易失存储、返回应答、主动上报最新值。

成功应答：

```json
{"id":"101","code":200,"msg":"succ"}
```

### 5.2 属性获取

平台下发：

```json
{"id":"102","version":"1.0","params":["DftVolume"]}
```

终端应答：

```json
{"id":"102","code":200,"msg":"succ","data":{"DftVolume":5}}
```

一次最多请求3个字段。终端必须返回当前RAM中真正生效的值，不得返回尚未执行的目标值。

### 5.3 属性上报

终端上报：

```json
{"id":"103","params":{"DftVolume":{"value":5}}}
```

发生以下事件时必须主动上报：设备上线、设置成功、参数在本地发生变化、计划切换、故障恢复。无变化时建议每60秒至300秒发送一次心跳或状态字段，具体周期由双方确认。

## 6 功能字段定义

| 字段 | 类型 | 方向 | 范围 | 单位 | 定义和使用规范 | 当前状态 |
|---|---|---|---|---|---|---|
| DftEnable | int32 | 读写 | 0或1 | 无 | 参数控制总使能。0关闭业务输出，1允许按工作时段和音量参数运行。设置成功后必须上报。 | 已联调验证 |
| DftVolume | int32 | 读写 | 0至9 | 档 | 当前喇叭音量。0为静音，9为最大档。网页手动设置和当日音量计划均写此字段。 | 已实机验证 |
| DftStHour | int32 | 读写 | 0至23 | UTC小时 | 默认工作开始小时，与DftStMinute组成UTC开始时间。 | 已联调验证 |
| DftStMinute | int32 | 读写 | 0至59 | 分钟 | 默认工作开始分钟。 | 已联调验证 |
| DtfEdHour | int32 | 读写 | 0至23 | UTC小时 | 默认工作结束小时。字段拼写以OneNET现有物模型DtfEdHour为准。 | 已联调验证 |
| DftEdMinute | int32 | 读写 | 0至59 | 分钟 | 默认工作结束分钟。 | 已联调验证 |
| Period | int32 | 兼容读写 | 0至3600 | 秒 | 旧版周期字段。终端现改为受信号机输入驱动，新业务不得继续依赖。 | 已验证；弃用 |
| RushTime | int32 | 兼容读写 | 0至3600 | 秒 | 旧版快行字段。保留仅用于兼容已部署固件。 | 已验证；弃用 |
| WalkTime | int32 | 兼容读写 | 0至3600 | 秒 | 旧版慢行字段。保留仅用于兼容已部署固件。 | 已验证；弃用 |
| ID | int32 | 只读 | 非负整数 | 无 | 终端固件编号或逻辑编号。定义需设备方最终确认，不作为OneNET device_name。 | 可读取 |
| Noise | int32 | 只读 | 非负整数 | 原始值 | 现场噪声采样值。是否换算为dB及标定公式需设备方提供。 | 可读取 |
| State | uint32 | 只读 | 0至2^32-1 | 位图 | bit为1表示对应异常；bit0设备异常、bit1 GPS异常、bit2 RTC电池欠压、bit3音频文件异常、bit4 Flash异常、bit5噪声传感器异常、bit6功放异常、bit7通信模块异常、bit8电源异常；其余保留。 | 可读取，位定义待终端最终确认 |

开始时间与结束时间相同视为无效时段。平台不得再通过三个已弃用周期字段模拟信号机；信号状态由3路数字输入或双方确认后的RS-485协议提供。

## 7 在线状态和业务状态

在线状态表示设备MQTT会话是否连接OneNET。State表示终端业务是否运行，DftEnable表示参数控制是否允许。三者不能互相替代。终端上线后应在5秒内主动上报State、DftEnable、DftVolume和所有工作参数，使平台不依赖历史缓存。

## 8 错误码

| code | 含义 | 终端处理 |
|---|---|---|
| 200 | 成功 | 参数已生效，可主动上报新值 |
| 400 | JSON或请求格式错误 | 不修改参数，msg说明错误位置 |
| 401 | 消息ID或版本不合法 | 不执行 |
| 404 | 字段或文件类型不存在 | 不执行 |
| 409 | 设备忙或文件传输状态冲突 | 平台延迟后重试 |
| 413 | Payload超过200字节 | 丢弃整帧并记录错误 |
| 422 | 类型、范围或业务关系错误 | 不修改参数 |
| 500 | 终端内部错误 | 保持原值，记录故障 |
| 507 | Flash空间不足或写入失败 | 中止文件传输并清理临时文件 |

## 9 文件传输协议

### 9.0 定时表归属和时段规则

当前发布版采用“平台调度”模式：七天计划只存于后端，平台到达时间点时写`DftVolume`，终端无需保存星期表。在此模式中，每条记录是一个音量切换点而不是起止区间，因此不存在区间重叠。

若后续启用“终端自主调度”模式，必须另行实现时段表命令；每条时段至少包含`seq/day/start/finish/volume/enable`。`seq`为同一天内1至16的稳定序号；同一天启用时段不得重叠；跨零点时段拆成两条；`start==finish`无效。终端应支持每天至少8条、目标16条。时区和夏令时由平台根据设备IANA时区转换，终端只接收UTC，不自行维护各国DST规则。两种调度模式不得同时生效。

### 9.1 文件要求

支持walk、rush和custom三类WAV文件。WAV格式固定为单声道、8kHz、8bit。慢行和快行音频分别不超过4秒，自定义音频不超过24秒，全部内容总时长不超过32秒。传输前平台必须校验WAV文件头、长度和CRC32。

文件传输不使用物模型属性字段，采用双方确认后的OneNET自定义Topic。建议逻辑消息类型为file begin、file chunk、file end和file ack；在OneNET自定义Topic未确认前，后端只提供预检和分片规划，不允许显示传输成功。

### 9.2 分片规则

- 原始分片固定96字节，Base64后最多128字符。
- 每帧只携带一个分片，使用停等方式；收到对应ACK后才发送下一片。
- 分片序号从0开始，总片数在begin帧中给出。
- 终端不得把完整文件缓存在RAM，应边收边写临时Flash区。
- end帧后校验文件大小和CRC32，成功后再原子切换有效文件。

开始帧：

```json
{"v":1,"t":"fb","id":"a1b2c3d4","k":"walk","s":4096,"n":43,"c":"1234abcd"}
```

分片帧：

```json
{"v":1,"t":"fc","id":"a1b2c3d4","n":0,"d":"BASE64数据"}
```

结束帧：

```json
{"v":1,"t":"fe","id":"a1b2c3d4"}
```

应答帧：

```json
{"v":1,"t":"fa","id":"a1b2c3d4","n":0,"code":200}
```

文件分片超时5秒，单片最多重试3次。重试必须使用相同transfer id和序号。终端收到重复分片时应返回成功ACK，不得重复追加写入。

## 10 后端接口预留

| 方法和路径 | 用途 | 状态 |
|---|---|---|
| GET `/api/devices/{id}/protocol/` | 获取字段、范围、200字节限制和文件能力清单 | 已实现 |
| GET `/api/devices/{id}/onenet/parameters/?keys=DftVolume` | 主动读取终端真实属性 | 已实现 |
| POST `/api/devices/{id}/onenet/parameters/` | 设置一个或多个真实属性 | 已实现 |
| PUT `/api/devices/{id}/schedule/` | 保存七天计划并下发当天当前音量 | 已实现 |
| POST `/api/devices/{id}/file-transfer/prepare/` | 校验文件元数据并生成分片参数 | 已实现，暂不发送 |
| 文件begin、chunk、end发布接口 | 向确认后的自定义Topic发送文件 | 待双方确认Topic和Flash策略 |

文件预检请求示例：

```json
{"kind":"walk","filename":"walk.wav","size":4096,"crc32":"1234abcd"}
```

返回transportReady为false表示只完成预检，不能视为文件已到达终端。

## 11 联调验收流程

1. 验证MQTT上线和离线事件，断网后平台在合理时间内显示离线。
2. 终端上线后主动上报完整工作参数和State。
3. 对每个读写字段执行原值读取、相邻值设置、主动读取确认、原值恢复、再次确认。
4. 检查每个下行和上行Payload长度均不超过200字节。
5. 验证非法类型、越界值、未知字段和超长帧均被拒绝且不改变终端状态。
6. 验证重复消息ID不会造成重复写Flash或重复执行。
7. 文件传输分别测试正常、丢包、重复分片、乱序、CRC错误、空间不足和断电恢复。
8. 后端只有在终端真实值确认后才向前端显示成功；超时必须显示未确认。

## 12 当前待设备方确认事项

- 正式发布前仍应执行一次不改变现场最终配置的回归：读取原值、写相邻值、读取确认、恢复原值；这属于发布验收，不影响现有“已联调验证”结论。
- 确认ID字段的业务含义和取值范围。
- 提供Noise原始值到dB的标定公式和有效范围。
- 确认State位图中bit0至bit8定义及保留位处理。
- 确认终端自主时段表是否需要；如需要，确认`seq`、每天16条、拒绝重叠和跨零点拆分规则。
- 确认文件自定义Topic、Flash临时区大小、文件切换方式和断电恢复策略。
- 确认WAV文件名与播放逻辑的最终映射。
- 明确3路数字输入的电气类型、电平、隔离和有效极性；如使用RS-485，提供厂商协议、波特率、地址、校验、寄存器/命令及超时重试规则。

## 13 现有功能与缺口总表

| 网页功能 | 当前后端接口 | 当前是否到终端 | 终端需要补充 | 结论 |
|---|---|---:|---|---|
| ON/OFF | `POST /api/devices/{id}/onenet/parameters/`，字段`DftEnable` | 是 | 稳定实现set/get/post及请求ID应答 | 已接入，读取仍可能超时 |
| 当前音量 | 同上，字段`DftVolume` | 是 | 设置后主动上报真实值 | 已实机验证 |
| 工作起止时间 | 同上，4个时间字段 | 是 | 已有整组读写成功记录；平台按设备时区转UTC | 已联调验证 |
| 信号周期 | 旧字段`Period/RushTime/WalkTime` | 不再由新前端写入 | 改由信号机3路输入或RS-485驱动 | 兼容保留、业务弃用 |
| 每周音量计划 | `PUT /api/devices/{id}/schedule/` | 只下发当天当前`DftVolume` | 无需理解星期；只接收当天平台下发值 | 已接入，调度器需常驻运行 |
| 街道名称 | `PATCH /api/devices/{id}/audio-config/` | 否 | 选择“终端TTS文本”或“平台生成WAV”方案 | 目前仅数据库字段 |
| 浏览器试听街道名 | 无终端接口 | 否 | 不需要；当前由浏览器SpeechSynthesis完成 | 不是终端功能 |
| 慢行/快行/自定义声音 | `POST /audio-files/`服务端复验并生成分片计划 | 尚未发送 | 确认Topic、ACK、Flash暂存、CRC、激活和播放 | 平台预检完成，待联合传输测试 |
| 修改蓝牙名称 | `POST /api/devices/{id}/rename-bluetooth/` | 否 | 蓝牙名称读写命令、持久化、重启行为 | 当前仅改数据库，不能称终端成功 |
| 蓝牙连接/配对 | 无 | 否 | 决定是否需要配对PIN、连接状态和断开命令 | 尚未定义 |
| 声音测试播放/停止 | 无 | 否 | 指定声音播放、停止、忙状态应答 | 尚未实现 |
| 文件清单/版本 | 无 | 否 | 返回每个声音文件的大小、CRC和激活状态 | 尚未实现 |

## 14 SoundGate后端HTTP接口

所有接口均要求`Authorization: Token <登录Token>`，只能访问当前账号拥有的设备。HTTP响应成功只代表后端完成相应阶段；涉及终端的操作必须通过`terminalConfirmed`区分“已受理”和“已在终端生效”。

### 14.1 获取协议能力

`GET /api/devices/{deviceId}/protocol/`

响应：

```json
{"version":"1.0","maxFrameBytes":200,"properties":{},"fileTransfer":{"status":"reserved","rawChunkBytes":96},"bluetooth":{"status":"pending_terminal_protocol","maxNameBytes":32},"streetAudio":{"status":"local_only"},"audio":{"status":"pending_terminal_protocol"}}
```

关键返回参数：

| 参数 | 类型 | 含义 |
|---|---|---|
| `version` | string | 协议版本 |
| `maxFrameBytes` | int | 终端MQTT Payload硬上限 |
| `properties` | object | 字段类型、读写权限、范围和验证状态 |
| `fileTransfer.status` | string | `reserved/ready/disabled` |
| `fileTransfer.rawChunkBytes` | int | 每个文件分片的原始字节数 |
| `bluetooth.status` | string | 当前为`pending_terminal_protocol`，后端入口存在但终端协议未接通 |
| `streetAudio.status` | string | 当前为`local_only`，只保存平台数据 |
| `audio.status` | string | 当前为`pending_terminal_protocol`，文件与播放命令尚未接通 |

### 14.2 主动读取终端属性

`GET /api/devices/{deviceId}/onenet/parameters/?keys=DftVolume,State`

响应：

```json
{"parameters":{"DftVolume":{"value":6,"displayValue":6,"name":"喇叭音量","dataType":"int32"},"State":{"value":1,"displayValue":1,"name":"设备状态","dataType":"int32"}}}
```

`value`必须来自本次终端响应。终端超时应返回`502`及`code=onenet_error`，不得以数据库值、期望值或历史缓存冒充本次读取值。

### 14.3 设置终端属性

`POST /api/devices/{deviceId}/onenet/parameters/`

请求示例：

```json
{"DftEnable":1,"DftVolume":6}
```

新业务允许参数：`DftEnable`、`DftVolume`、`DftStHour`、`DftStMinute`、`DtfEdHour`、`DftEdMinute`。`Period`、`RushTime`、`WalkTime`仅为兼容旧固件保留，前端不再提交。

产品ID、设备名和参数名都计入200字节总长度。同一次请求参数较多且组包超限时，后端必须在发布前拒绝；调用方应拆成多个不超过200字节的请求，不能截断JSON或部分发送同一帧。

当前响应除原始OneNET结果外，已明确给出受理和确认状态：

```json
{"accepted":true,"terminalConfirmed":false,"applied":{},"transport":"device_property","frameBytes":101}
```

| 参数 | 类型 | 含义 |
|---|---|---|
| `accepted` | bool | OneNET是否接受请求 |
| `terminalConfirmed` | bool | 终端是否已应答且真实读取一致 |
| `requestId` | string | 与MQTT请求和终端应答关联的ID；当前后端尚未统一提供 |
| `applied` | object | 终端确认后的真实值；未确认时必须为空 |

当前后端已经发起真实属性设置，并且不会把OneNET受理冒充终端确认；`requestId`关联和服务端主动复核仍需补齐，前端目前通过轮询主动读取确认开关状态。

### 14.4 周音量计划

`PUT /api/devices/{deviceId}/schedule/`

请求：

```json
{"slots":[{"weekday":1,"time":"07:00","volume":5},{"weekday":1,"time":"20:00","volume":2}]}
```

响应：

```json
{"slots":[{"id":1,"weekday":1,"time":"07:00","volume":5}],"currentDispatch":{"weekday":1,"time":"07:00","volume":5,"transport":"device_property"},"dispatchError":null}
```

`weekday`只属于平台数据库，取值1至7。终端不保存七天计划；平台在对应日期和时间通过`DftVolume`下发当天值。`currentDispatch`为空表示当前没有已生效时段，`dispatchError`非空表示保存成功但本次终端下发失败。

### 14.5 街道名称与音频配置

`GET /api/devices/{deviceId}/audio-config/`

当前响应：

```json
{"streetName":"中山路","walk_file_name":"","rush_file_name":"","custom_file_name":"","updated_at":"2026-09-23T10:00:00+08:00","delivery":"local_only","terminalConfirmed":false}
```

`PATCH /api/devices/{deviceId}/audio-config/`

当前请求：

```json
{"streetName":"中山路"}
```

当前接口只写数据库，不会下发终端，现已返回：

```json
{"streetName":"中山路","terminalConfirmed":false,"delivery":"local_only"}
```

设备方必须在以下方案中确认一种：

- 方案A：终端具备TTS，平台下发UTF-8街道文本，终端存储并播报。
- 方案B：终端不具备TTS，平台把街道文本生成符合规格的WAV，再走文件传输协议。

在方案未确认前，`streetName`只能作为平台显示信息，不能声称已同步终端。

### 14.6 修改蓝牙名称

`POST /api/devices/{deviceId}/rename-bluetooth/`

当前请求：

```json
{"bluetoothName":"SoundGate-Demo","password":"<后端管理密码>"}
```

`password`是SoundGate后端管理员校验信息，只能在HTTPS请求中使用，绝不能进入MQTT Payload。当前接口仅修改数据库，并用阶段化响应明确标记终端未确认：

```json
{"bluetoothName":"SoundGate-Demo","accepted":true,"terminalConfirmed":false,"delivery":"pending_terminal_protocol"}
```

终端协议完成后，只有终端返回成功并主动读取名称一致时，`terminalConfirmed`才可为`true`。

### 14.7 文件预检

`POST /api/devices/{deviceId}/file-transfer/prepare/`

请求：

```json
{"kind":"walk","filename":"walk.wav","size":4096,"crc32":"1234abcd"}
```

响应：

```json
{"transferId":"a1b2c3d4","rawChunkBytes":96,"totalChunks":43,"maxFrameBytes":200,"worstCaseChunkFrameBytes":181,"beginFrame":{"v":1,"t":"fb","id":"a1b2c3d4","k":"walk","s":4096,"n":43,"c":"1234abcd"},"transportReady":false}
```

该接口只处理文件元数据，不接收文件内容。`transportReady=false`时前端不得显示“已上传”或“已发送到设备”。

### 14.8 文件和声音接口

服务端WAV上传复验已经实现；终端传输、进度、播放和文件清单仍是对接合同，在自定义Topic联合验证前不得提前声称可用：

| 方法和路径 | 请求 | 成功响应 | 用途 |
|---|---|---|---|
| `POST /api/devices/{id}/audio-files/` | `multipart/form-data`: `kind,file` | 大小、时长、格式、CRC32、分片计划 | **已实现**：上传并服务端复验WAV，不代表终端已更新 |
| `POST /api/devices/{id}/file-transfers/` | `fileId,kind` | `transferId,status=queued` | 创建终端传输任务 |
| `GET /api/devices/{id}/file-transfers/{tid}/` | 无 | 状态、已确认分片、总分片、失败原因 | 查询传输进度 |
| `POST /api/devices/{id}/file-transfers/{tid}/cancel/` | 无 | `status=cancelled` | 中止传输并通知终端清理临时数据 |
| `POST /api/devices/{id}/audio/play/` | `kind` | 请求ID、终端确认状态 | 测试播放指定声音 |
| `POST /api/devices/{id}/audio/stop/` | 无 | 请求ID、终端确认状态 | 停止测试播放 |
| `GET /api/devices/{id}/audio/manifest/` | 无 | 三类文件的大小、CRC、版本、激活状态 | 核对终端真实文件 |

2026年10月联调样本经服务端同等规则验证：

| 文件 | 大小 | 时长 | 格式 | CRC32 | SHA-256 |
|---|---:|---:|---|---|---|
| `rush.wav` | 21764字节 | 2.000秒 | PCM / 单声道 / 8kHz / 8bit | `0541c2fc` | `f04a567fc54853512460e1964f4967988ce785b53f6a6519c06c3e956c392bfb` |
| `walk.wav` | 29764字节 | 3.000秒 | PCM / 单声道 / 8kHz / 8bit | `d69e04ad` | `6d6b098cef40f74101ad869839504dfb33c2399be0f4e0fe303a04f5864c9f4a` |

两个样本均符合`walk/rush ≤4秒`约束。它们只用于指定设备的联调，不随公开源码仓库发布。

## 15 终端MQTT扩展接口

以下是SoundGate根据网页功能提出的终端侧需求。属性接口继续使用OneJSON标准Topic；蓝牙、文本、声音和文件命令需要OneNET支持的自定义Topic。建议下行和上行分别为：

```text
下行：soundgate/{pid}/{device}/cmd/down
上行：soundgate/{pid}/{device}/cmd/up
```

最终Topic必须由双方在OneNET产品中验证后固化。所有帧使用紧凑JSON、QoS 1、UTF-8，且不得超过200字节。

### 15.1 通用ACK

终端对每个扩展命令返回：

```json
{"v":1,"t":"ack","id":"b101","code":200,"msg":"succ"}
```

`id`必须原样返回；`code`沿用第8节；`msg`建议不超过32个ASCII字符。成功ACK表示命令已经在终端完成，不是“已经收到准备处理”。耗时命令可先返回`code=202,msg=processing`，完成后再以相同ID返回最终ACK。

### 15.2 设置蓝牙名称

平台下行：

```json
{"v":1,"t":"bt_set","id":"b101","name":"SoundGate-Demo"}
```

终端成功响应：

```json
{"v":1,"t":"ack","id":"b101","code":200,"msg":"succ"}
```

参数规范：

| 参数 | 类型 | 规则 |
|---|---|---|
| `name` | string | UTF-8长度1至32字节；建议只用ASCII字母、数字、`-`和`_` |

终端收到后必须校验长度、写入非易失存储、更新BLE广播名称，并明确是否需要重启蓝牙协议栈。管理密码不属于该MQTT命令。

### 15.3 读取蓝牙信息

平台下行：

```json
{"v":1,"t":"bt_get","id":"b102"}
```

终端上行：

```json
{"v":1,"t":"bt_info","id":"b102","name":"SoundGate-Demo","conn":0}
```

`conn`：0未连接，1已连接。若固件不支持查询连接状态，可暂时省略该字段，但必须返回真实广播名称。

### 15.4 设置街道文本（仅TTS方案）

平台下行：

```json
{"v":1,"t":"street_set","id":"s101","text":"中山路"}
```

终端响应通用ACK，并在成功后支持读取：

```json
{"v":1,"t":"street_get","id":"s102"}
```

```json
{"v":1,"t":"street_info","id":"s102","text":"中山路"}
```

`text`必须是合法UTF-8，建议限制为96字节；组包后仍以200字节总上限为准。若终端没有TTS能力，本组接口整体不实现，街道播报改用WAV文件。

### 15.5 查询声音文件清单

一次只查询一种文件，避免响应超过200字节。

平台下行：

```json
{"v":1,"t":"audio_get","id":"a101","k":"walk"}
```

终端上行：

```json
{"v":1,"t":"audio_info","id":"a101","k":"walk","s":4096,"c":"1234abcd","active":1}
```

| 参数 | 含义 |
|---|---|
| `k` | `walk/rush/custom` |
| `s` | 当前文件总字节数；不存在时为0 |
| `c` | 当前文件CRC32，小写8位十六进制；不存在时为空串 |
| `active` | 1当前有效，0不存在、未激活或无效 |

### 15.6 测试播放声音

平台下行：

```json
{"v":1,"t":"audio_play","id":"a102","k":"walk"}
```

终端完成启动播放后返回通用ACK。若文件不存在返回`404`，正在播放或设备忙返回`409`。测试播放不得永久改变`DftEnable`、计划或当前音量配置。

停止播放：

```json
{"v":1,"t":"audio_stop","id":"a103"}
```

终端停止后返回通用ACK；重复停止必须幂等返回成功。

### 15.7 文件传输

沿用第9节`fb/fc/fe/fa`帧。建议增加终端主动状态帧：

```json
{"v":1,"t":"fs","id":"a1b2c3d4","next":12,"code":202}
```

`next`表示终端期望的下一分片序号，可用于断线续传。文件传输完成后，终端必须先返回最终`fa code=200`，再响应`audio_get`并返回新文件的大小、CRC和`active=1`，平台才能把任务标记为成功。

### 15.8 终端启动后的完整上报

终端每次上线后应完成：

1. 通过OneJSON属性上报`State`、`DftEnable`、`DftVolume`和已实现工作参数。
2. 平台主动调用`bt_get`获取真实蓝牙名称。
3. 平台分别调用三次`audio_get`获取`walk/rush/custom`文件清单。
4. TTS方案启用时，平台调用`street_get`获取真实街道文本。

### 15.9 信号机扩展接口

终端硬件改板前必须由甲方/信号机厂商书面确认以下一种接入方式；平台不得凭猜测定义现场电气参数。

**数字输入最低需求：**3路隔离输入，分别为总开关、绿灯和红灯。确认表必须包含输入电压范围、干接点/湿接点、有效高低电平、公共端、隔离耐压、滤波/去抖时间、红绿同时有效时的安全行为。终端只上报归一化状态，不上传原始危险电平。

**RS-485最低需求：**接口应可配置波特率、数据位、停止位、奇偶校验、从站地址、响应超时和重试次数。信号机厂商必须提供帧头、长度、命令字/寄存器、字节序、CRC算法、绿/红/闪烁状态编码、异常码和轮询上限。协议未取得前，后端能力状态固定为`requirements_pending`，前端只显示待确认，不提供虚假的保存按钮。

终端向平台上报信号状态的拟议短帧如下，最终字段在RS-485/IO方案确认后冻结：

```json
{"v":1,"t":"sig","id":"g101","en":1,"r":0,"g":1,"fl":0,"src":"io"}
```

`src`取`io`或`485`；`en/r/g/fl`均为0或1。该状态仅用于监控，不代替终端本地实时联动，网络中断时终端仍必须按现场信号安全运行。

## 16 双方开发任务清单

### 16.1 后端需要补齐

- 修改蓝牙名称接口不得再把数据库保存当作终端成功；增加MQTT下发、ACK等待和`bt_get`复核。
- 街道名称接口增加`delivery`和`terminalConfirmed`；根据设备能力选择TTS命令或WAV生成与传输。
- 服务端WAV复验和文件持久化已完成；继续补充总时长32秒联动校验和文件版本历史。
- 实现文件传输任务、MQTT发布、ACK状态机、超时重试、进度查询、取消和失败清理。
- 实现`audio_get/audio_play/audio_stop`对应HTTP接口。
- 对所有终端操作返回统一的`accepted/terminalConfirmed/requestId/applied/error`结构。
- 保存终端真实蓝牙名称、文件CRC、大小、激活状态和最后确认时间，目标值与真实值分开存储。

### 16.2 终端需要补齐

- 保持OneJSON全部字段set/get/post闭环稳定，并配合正式发布前的恢复原值回归。
- 实现扩展Topic订阅和通用ACK，所有命令按ID幂等。
- 实现蓝牙名称持久化、广播更新和真实名称读取。
- 确认街道名采用TTS文本还是WAV音频，并实现对应命令。
- 实现三类WAV的Flash分区、分片写入、CRC、原子切换、断电恢复和清单读取。
- 实现声音测试播放和停止，不影响正式运行配置。
- 所有收发帧组包前检查UTF-8字节长度，超过200字节整帧拒绝。

### 16.3 双方必须先确认

- OneNET是否允许并如何配置建议的自定义Topic；若Topic命名受限，以OneNET实际配置替换第15节Topic。
- 蓝牙名称最大UTF-8字节数、允许字符、是否需要重启及配对PIN是否可远程修改。
- 终端是否具备TTS；若具备，支持的编码、字库和最大文本长度。
- Flash布局、最大文件大小、断电续传方式及旧文件回滚策略。
- 音频播放优先级：测试播放、正常信号播放和紧急播报发生冲突时谁优先。
- 声音文件名是否固定为`walk.wav/rush.wav/custom.wav`，还是仅按`kind`映射。
- 文件联调时间、测试设备名、失败日志获取方式，以及由谁在OneNET创建和授权自定义Topic。
- 3路数字输入的电气规范；如改用RS-485，须先取得信号机厂商完整协议再安排硬件改板。

## 17 项目结构核对与测试记录

本节记录协议与当前仓库的对应关系，防止把设计目标误写成已实现功能。

### 17.1 已检查的实现位置

| 范围 | 当前实现 |
|---|---|
| DRF路由与接口 | `backend/devices/urls.py`、`backend/devices/views.py` |
| 参数校验与账号隔离 | `backend/devices/serializers.py`、`backend/devices/models.py` |
| OneNET读写与200字节组帧 | `backend/devices/onenet.py` |
| 协议能力与文件预检 | `backend/devices/device_protocol.py` |
| 当日音量计划调度 | `backend/devices/schedule_dispatch.py` |
| 前端API与状态交互 | `frontend/src/api/devices.ts`、`frontend/src/services/deviceService.ts` |
| 蓝牙、街道名、WAV页面 | `DeviceSettingsView.vue`、`AudioSettingsView.vue`、`AudioUploader.vue` |

### 17.2 2026-09-23自动化结果

- DRF测试15项全部通过，包括账号设备隔离、OneNET模拟交付、字段类型和范围、UTF-8蓝牙名称限制、未接通能力状态及文档MQTT示例帧。
- 文档中的23个单行MQTT JSON示例均可解析，最大示例为82字节，无一超过200字节。
- Django系统检查通过，迁移状态无遗漏。
- Vue TypeScript检查和Vite生产构建通过。
- 本轮没有向真实终端发送控制或文件数据；OneNET在线状态、设备ACK、声音播放和Flash写入必须在真实联调环境另行验收。

### 17.3 本轮修正

- 后端现在统一拒绝未知字段、只读字段、非整数和超出协议清单范围的属性值，再执行OneNET请求。
- `Period/RushTime/WalkTime`的平台校验上限与协议清单统一为3600；其业务关系仍标为待设备方确认。
- 蓝牙名称改为按UTF-8字节校验，最大32字节，不再仅按字符数判断。
- 蓝牙和街道名称接口明确返回`terminalConfirmed=false`，前端不再提示已经修改终端。
- 协议能力接口明确暴露蓝牙、街道音频和声音文件功能的当前状态，未接通能力不会伪装成可用。

### 17.4 2026-10-23反馈闭环

- 读取并核对《终端产品功能设计调试反馈(2026-10-08)》全部9页及红字批注。
- 根据9月23日和10月5日截图，将全部属性读写标为已有联调成功证据；不再保留“5个字段主动读取超时”或“待平台回归”的旧结论。
- 新前端停止提交`Period/RushTime/WalkTime`，信号机联动改为3路输入/RS-485待确认合同。
- 后端新增`POST /api/devices/{id}/audio-files/`，对WAV头、PCM、声道、采样率、位深、时长做服务端复验，计算CRC32并生成≤200字节的分片计划。
- `rush.wav`和`walk.wav`样本均通过复验；平台尚未向终端发送，联调成功必须以最终ACK和`audio_get`读回CRC一致为准。
- 能力清单新增时段归属、UTC转换、State位图和信号机接口状态，便于前端只展示真实能力。

截图证据逐项记录如下：

| 时间 | 操作 | 字段/数值 | OneNET结果 |
|---|---|---|---|
| 2026-09-23 14:49:21 | 写 | `DftVolume=6` | `code=200,msg=user succ` |
| 2026-09-23 14:49:34 | 读 | `DftVolume` | 返回`DftVolume=6` |
| 2026-09-23 14:49:41 | 读 | `Noise` | 成功 |
| 2026-10-05 14:31:21 | 读 | `DftEnable,DftStHour` | 成功 |
| 2026-10-05 14:31:39 | 读 | `DftEnable,DftStHour,DftStMinute` | 成功 |
| 2026-10-05 14:36:10 | 写 | `WalkTime=22` | 成功 |
| 2026-10-05 14:45:08 | 写 | `Period=90` | 成功 |
| 2026-10-05 14:45:34、14:49:51、15:07:11 | 读 | `DftEdMinute,DftEnable,DftStHour,DftStMinute,DftVolume,DtfEdHour,ID,Noise,Period,RushTime,State,WalkTime` | 三次均成功 |
| 2026-10-05 14:49:12 | 写 | `DftEdMinute=30,DftVolume=9,DftEnable=1,DftStHour=8,Period=80,DtfEdHour=20,RushTime=11,DftStMinute=0,WalkTime=22` | 成功 |
| 2026-10-05 15:07:02 | 写 | `DftEdMinute=30,DftVolume=6,DftEnable=1,DftStHour=6,Period=60,DtfEdHour=22,RushTime=11,DftStMinute=20,WalkTime=22` | 成功 |

“操作记录成功”证明OneNET与终端的对应读写路径已工作；运行时平台仍必须读取真实值，不能以期望值或仅HTTP受理结果代替终端状态。

## Expectations

本节是本协议的完成判定，不描述实现方式。任何一项未满足，都不能宣布终端与平台联调完成。

### Success scenarios

1. 平台设置一个可写属性后，终端返回与请求ID对应的成功应答，并主动上报同一字段的真实生效值；平台主动读取该字段时得到相同数值。
2. 终端上线后5秒内上报`State`、`DftEnable`、`DftVolume`及全部已实现工作参数，平台显示值与终端当前RAM中的生效值一致。
3. `DftEnable`、`DftVolume`及4个工作起止时间字段均能完成“读取原值—设置相邻合法值—读取确认—恢复原值—再次确认”的闭环；三个旧周期字段只做兼容回归。
4. 每个终端收发的MQTT Payload按UTF-8计算均不超过200字节。
5. 文件正常传输时，终端按序确认全部分片，校验文件长度和CRC32成功后一次性切换有效文件，读取或播放得到新文件。
6. 设备断开MQTT连接后，平台最终显示离线；设备重新连接后，平台重新获得本次连接对应的真实参数，不沿用无法确认的历史值。
7. 前端只在终端真实值确认后显示操作成功；等待期间禁止重复提交同一设备的冲突操作，超时显示“未确认”而不是“失败后已回滚”或“成功”。
8. 修改蓝牙名称时，终端先返回匹配请求ID的成功ACK；随后`bt_get`返回的新名称与目标名称一致，平台才显示已生效。
9. 街道名称按双方选定的唯一方案完成闭环：TTS方案以`street_get`读回文本确认，WAV方案以文件大小、CRC和`active=1`确认。
10. WAV文件必须同时通过服务端格式复验、终端分片接收、长度/CRC校验和`audio_get`清单复核，才显示上传成功。
11. `audio_play`和`audio_stop`均返回匹配请求ID的ACK；测试播放前后正式工作参数和周计划保持不变。

### Failure scenarios

1. OneNET接口返回请求已受理，但终端没有应答或主动读取值未变化，平台却显示设置成功。
2. 终端返回成功应答，但应答ID与下行请求ID不一致，平台仍把它关联到当前操作。
3. 终端收到非法类型、越界值、未知字段或业务关系不合法的参数后修改了RAM或Flash中的原值。
4. 同一消息ID或同一文件分片重发时，终端重复执行控制、重复写Flash或重复追加文件数据。
5. 文件缺片、乱序、CRC错误、空间不足或中途断电后，终端仍把不完整文件切换为有效文件。
6. 平台把MQTT在线状态、`State`和`DftEnable`显示为同一个状态，导致“在线但停止”或“离线但历史运行值为1”被误判。
7. 只完成文件预检或分片规划时，接口或前端显示“文件已传输到终端”。
8. 蓝牙名称只写入平台数据库、未收到终端ACK和读回结果，接口却返回终端修改成功。
9. WAV只通过浏览器校验，服务端未复验或终端未确认，接口却返回上传成功。
10. 终端返回文件最终ACK后，`audio_get`得到的大小、CRC或激活状态与目标文件不一致，平台仍把任务标记成功。
11. 浏览器语音合成能够朗读街道名称，就被视为终端已经收到并保存街道名称。

### Must-nots

1. 任一终端收发Payload不得超过200字节；超长帧必须整帧拒绝，且不得产生部分参数更新。
2. Payload不得包含OneNET AccessKey、用户Token、产品密钥、设备密钥或其他鉴权凭据。
3. 在终端真实应答或主动读取确认前，平台不得把目标值写成真实值或向用户显示已生效。
4. 参数校验必须是全有或全无：一个请求包含多个字段时，任一字段不合法则所有字段均不得修改。
5. 文件CRC32和长度校验完成前不得覆盖当前有效音频；失败时必须保留旧文件并清理临时数据。
6. 未确认Topic、Flash策略和断电恢复方案前，不得启用正式文件发送接口。
7. 不得把`ID`字段当作OneNET `device_name`，也不得擅自修正现有物模型字段`DtfEdHour`的拼写。
8. 对标为“待确认”的扩展能力不得在文档、后端清单或前端中标记为已完成联调；属性字段的成功证据与音频/蓝牙/RS-485扩展能力必须分别判断。
9. 后端管理员密码只用于HTTP接口鉴权，不得写入MQTT Payload、日志或发送给终端。
10. 测试播放不得永久修改`DftEnable`、`DftVolume`、工作时段或周计划。
11. 浏览器本地预览不得作为终端播放、终端TTS或文件传输成功的证据。

### Open questions

以下问题仍会改变完成边界，双方确认后应更新本节并重新生成断言：

- `State`位图bit0至bit8的最终定义及保留位规则。
- 开始时间等于结束时间表示全天工作还是全天停止。
- 已部署旧固件中`Period`、`RushTime`和`WalkTime`的停止支持时间；新硬件由信号机接口驱动。
- 文件自定义Topic、Flash临时区、原子切换和断电续传方案。
- `Noise`的物理单位、标定公式和有效范围。
- 信号机3路输入的电气规格，或RS-485厂商协议全文。
