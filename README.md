# SoundGate

交通信号灯与人行横道声音提示终端的设备管理平台。前端提供设备、音量计划、工作参数、街道语音和蓝牙配置界面；后端负责账号隔离、MySQL持久化及OneNET设备通信。

> 本仓库不包含OneNET密钥、用户标识、设备Token或生产数据库。真实凭据只应保存在本地`backend/.env`或部署平台的Secret中。

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Pinia、Vue Router、Element Plus、Axios
- 后端：Python、Django、Django REST Framework、Token Authentication
- 数据库：MySQL 8.4；自动化测试使用隔离的SQLite内存库
- 设备通信：中国移动OneNET、MQTT/OneJSON、HTTP设备管理接口

## 功能状态

| 功能 | 状态 |
|---|---|
| 登录、注册、账号设备隔离 | 已实现 |
| OneNET设备发现与导入 | 已实现 |
| 设备在线状态与属性同步 | 已实现 |
| 开关、音量、工作时段和信号参数 | 已接入；成功状态以终端真实上报为准 |
| 每周音量计划 | 已实现；平台只在对应日期下发当天音量 |
| 街道名称 | 当前只保存平台配置，未同步终端 |
| 蓝牙名称 | 当前只保存平台配置，终端协议待接入 |
| WAV文件传输与测试播放 | 协议已设计，后端和终端传输链路待实现 |

详细协议和未完成边界见[MQTT通信协议](docs/SoundGate终端平台MQTT通信协议.md)。

## 项目结构

```text
soundgate/
├── backend/                 Django REST Framework后端
│   ├── devices/             设备模型、API、OneNET适配与测试
│   └── soundgate/           Django项目配置
├── frontend/                Vue 3 + TypeScript前端
├── docs/                    MQTT协议与可执行断言
├── tools/                   文档及OneNET辅助测试工具
├── docker-compose.yml       本地MySQL服务
└── README.md
```

## 本地运行

### 1. 配置环境

```bash
cp backend/.env.example backend/.env
```

编辑`backend/.env`，至少修改Django密钥、数据库密码和设备管理密码。需要连接OneNET时，再填写自己的产品ID和鉴权信息。不要提交该文件。

### 2. 启动MySQL和后端

```bash
docker compose up -d mysql
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
python backend/manage.py migrate
python backend/manage.py runserver 127.0.0.1:8000
```

如需演示数据，必须显式提供本地演示密码：

```bash
SOUNDGATE_SEED_PASSWORD='replace-with-a-strong-local-password' \
  python backend/manage.py seed_devices
```

### 3. 启动前端

```bash
cd frontend
npm ci
npm run dev
```

浏览器访问`http://127.0.0.1:5173/`。Vite会把`/api`代理至`127.0.0.1:8000`。

### 4. 启动后台任务

连接真实OneNET环境时，根据需要分别启动：

```bash
backend/.venv/bin/python backend/manage.py run_onenet_listener
backend/.venv/bin/python backend/manage.py run_schedule_dispatcher
```

## 主要API

- `POST /api/auth/register/`、`POST /api/auth/login/`
- `GET /api/devices/`
- `GET /api/devices/onenet/available/`
- `POST /api/devices/onenet/import/`
- `POST /api/devices/onenet/sync/`
- `GET/POST /api/devices/{device_id}/onenet/parameters/`
- `GET/PUT /api/devices/{device_id}/schedule/`
- `GET/PATCH /api/devices/{device_id}/audio-config/`
- `POST /api/devices/{device_id}/rename-bluetooth/`
- `GET /api/devices/{device_id}/protocol/`

## 测试与构建

```bash
cd backend
.venv/bin/python manage.py test devices.tests --settings=soundgate.test_settings
.venv/bin/python manage.py check --settings=soundgate.test_settings
.venv/bin/python manage.py makemigrations --check --dry-run --settings=soundgate.test_settings

cd ../frontend
npm run build
```

测试不会连接业务MySQL，也不会向真实终端发送控制命令。

## 安全与隐私

- `.env`、虚拟环境、依赖目录、构建产物、Word导出文件和本地二进制均不会提交。
- 禁止在Issue、日志或截图中粘贴AccessKey、APIKey、设备密钥、Token及账号信息。
- 前端收到OneNET受理结果不等于终端已生效；必须等待真实属性读回或终端ACK。
- 安全问题请按[SECURITY.md](SECURITY.md)私下报告。

## 协议文档

- [SoundGate终端平台MQTT通信协议](docs/SoundGate终端平台MQTT通信协议.md)
- [MQTT协议可执行断言](docs/SoundGate终端平台MQTT通信协议.assertions.md)

## 许可证

当前仓库尚未授予开源许可证。除非仓库所有者另行添加许可证，否则保留全部权利。
