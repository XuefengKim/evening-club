# 今晚俱乐部 · Tonight Club

17 款适合朋友一起玩的浏览器小游戏：桌面对弈、纸牌，以及原创双人平台冒险《星港维修队》。支持本机局域网启动，也提供 Render 云部署配置；部署在云端后，玩家打开同一个网址即可进入，本地电脑无需开机。

## 云端部署（Render 免费配置）

[一键部署到 Render](https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2FXuefengKim%2Fevening-club)

1. 登录自己的 Render 账户，打开上面的入口，审核 Blueprint 中的服务配置并部署。仓库默认选择 **Free**，不创建付费数据库或磁盘。
2. 部署成功后，先用服务提供的 HTTPS 地址测试两台设备联机；不要求处于同一 Wi-Fi。
3. 需要自定义域名时，在 Render 服务的 Settings → Custom Domains 添加域名，然后按面板给出的记录修改 DNS。先验证新服务，再切换原域名。

`Dockerfile` 同时安装 Python 与 Node.js；一个容器启动统一入口及所有游戏后端，对外只开放统一入口。`PORT` 环境变量指定入口端口，Render 配置为 `10000`。云部署当前保持单实例，不能直接横向扩容，否则玩家可能进入不同的内存房间。为避免代码更新打断正在进行的对局，Blueprint 关闭自动部署，更新后在 Render 面板手动部署。

**免费版限制：**按 [Render 官方说明](https://render.com/docs/free)，服务闲置 15 分钟会休眠，下次访问约需一分钟唤醒；实例也可能随时重启。当前对局存于内存，《星港维修队》的进度存于临时文件，休眠、重启或重新部署后不能保证保留。免费额度耗尽会暂停服务。不要将它当作永久存档方案；稳定存档需要另接持久存储。

代码提供云部署配置，不代表已在你的 Render 账户上线。实际部署后仍需验证两设备联机、手机 Safari 布局、星港帧率与延迟；免费实例的流畅度尚未实测。

## 游戏清单

| 分区 | 游戏 | 数量 |
| --- | --- | ---: |
| 经典小游戏 | 四子连线、翻牌配对、骰子冒险、猜拳对决、数字拆弹、点格围城 | 6 |
| 扩展小游戏 | 井字棋、五子棋、黑白棋、拿石子、Hex 连线抢地、暗码对决 | 6 |
| 纸牌 | 疯狂八点、宫殿牌、六张高尔夫 | 3 |
| UNO | 带页面规则说明的 UNO 风格牌桌，支持人机 | 1 |
| 协作冒险 | 星港维修队：8 个递进关卡、磁力搬运、二段跳、时间脉冲 | 1 |

各游戏的规则和简化设定以页面内说明为准。桌面对弈和纸牌支持真人或人机；《星港维修队》需要两台设备分别控制两位角色。

## 安装与启动

需要 **Python 3.10+、Node.js 22+ 和 npm**。下载或克隆仓库后，在仓库目录运行。

macOS / Linux：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm --prefix apps/starport ci
.venv/bin/python start.py
```

Windows PowerShell：

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
npm --prefix apps/starport ci
.venv\Scripts\python.exe start.py
```

启动后，终端会显示本机地址和局域网地址。两台设备连接同一 Wi-Fi，打开终端打印的局域网网址，在大厅选择同一款游戏。默认入口为 `http://localhost:8780/`。

- 电脑需要保持开机，运行游戏的终端需保持打开；按 `Ctrl+C` 停止本次启动的全部服务。
- macOS 安装依赖后也可双击 `启动游戏.command`。
- 默认使用 8780–8789 端口。端口占用时启动器会报错，可以运行 `python start.py --port 18780` 换用另一组端口。
- 只在本机试玩可加 `--bind 127.0.0.1`。局域网游玩需要允许入口端口的网络连接，并避免使用隔离设备的访客 Wi-Fi。
- 游戏按局域网场景设计；游戏状态保留在服务进程中，《星港维修队》的已通关进度另存于 `.data/starport-progress.json`。

## 星港维修队 · 手机玩法

![手机横屏布局](docs/starport-mobile.png)

- 默认近景跟随本机角色，右上角小地图显示伙伴和目标；点「全图」查看整个关卡。
- 左侧移动，右侧跳跃和技能，可同时操作。横屏视野更宽，竖屏也支持。
- 搬运员可磁吸、搬运货箱；侦察员可二段跳，并释放冻结无人机的时间脉冲。
- 电脑支持 `A / D / W` 或方向键，`E / 空格` 使用技能。
- iPhone Safari 中可使用浏览器内沉浸布局。要移除 Safari 地址栏：在游戏页点「分享 → 添加到主屏幕」，如出现「作为网页 App 打开」选项则开启，再从主屏幕图标启动。
- 第一次从主屏幕启动时，建议先退出 Safari 页内的座位，再在网页 App 中接入。

手机布局经过桌面浏览器尺寸模拟与输入逻辑检查；iPhone 实体机 Safari、主屏幕启动和各设备手感仍需实际体验验证。

## 项目结构

```text
start.py             统一启动与关闭本次启动的子进程
gateway.py          统一页面、发现接口与 WebSocket 路由
apps/
  main/              原六款游戏的页面、服务与规则测试
  extra/             扩展六款游戏
  cards/             三款纸牌
  uno/               UNO 风格牌桌
  starport/          星港维修队与手机视图
scripts/check.py     完整检查入口
tests/test_stack.py  隔离端口的整栈联机验证
docs/                游戏预览图
```

所有游戏都从同一个入口进入：`/`、`/extra/`、`/cards/`、`/uno/`、`/starport/`。各后端仅监听本机回环地址，由统一入口转发连接。

## 检查

安装依赖后运行：

```bash
.venv/bin/python scripts/check.py
```

Windows 可将上面的 Python 路径替换为 `.venv\Scripts\python.exe`。

检查包括规则与完整对局模拟、翻牌难度递进及隐藏信息、星港角色动作与手机视图、多客户端 WebSocket，以及统一入口下 17 款游戏的接入。整栈测试会使用独立端口并在结束后关闭自身启动的进程。GitHub Actions 也会运行相同检查。

运行生成的日志、进程文件、依赖目录及玩家进度均由 `.gitignore` 排除。
