# OneNET C 属性设置测试

该程序直接调用 OneNET 属性设置接口，用来区分调用语言问题和终端应答问题。密钥只从环境变量读取，不写入源码。

```bash
cc set_property.c -o set_property $(curl-config --cflags --libs)
set -a
source ../../backend/.env
set +a
./set_property device-b 6
```

参数依次为设备名称和音量，音量仅允许 0 到 9。
