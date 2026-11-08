# 腾讯云部署与运维

2026-11-08，网站部署到腾讯云上海轻量应用服务器，入口为 <https://lovecollection.online/>。使用单个应用实例，Python 提供页面及 WebSocket，Node.js 作为星港子进程，由 systemd 管理启动和重启，Nginx 提供 HTTPS。

## 当前运行方案

| 项目 | 配置 |
| --- | --- |
| 服务器 | Ubuntu 24.04，4 核 / 4GB，40GB SSD，3Mbps，300GB 月流量包 |
| 运行环境 | Python 3.12；Node.js 22，部署时版本为 22.23.4 |
| 已上线应用版本 | `3870f6168526505a302041d12e7db5901e038bdd`；后续以服务器 `current` 指向为准 |
| 外部入口 | Nginx 80 / 443；HTTP 跳转 HTTPS |
| 应用监听 | `127.0.0.1:10000`；星港使用内部回环端口，不对公网开放 |
| 进程管理 | `evening-club.service`，开机启动、异常重启，内存上限 2GB |
| 证书 | Let's Encrypt，Certbot 定时续期；首次证书到期日为 2027-02-06 |
| 发布方式 | 人工选择明确提交、安装依赖、检查后切换；没有配置 GitHub 自动部署 |

服务器当时无法连接 Docker Hub，因此采用原生运行环境；仓库的 Dockerfile 仍用于 CI 和 Render。不要直接横向扩容：牌桌在单实例内存中，多个实例不会共享房间。

```text
浏览器 HTTPS / WSS
    → Nginx
    → Python 127.0.0.1:10000
        → 对弈、纸牌、UNO
        → Node.js 星港子进程
```

## 目录和配置

| 路径 | 用途 |
| --- | --- |
| `/opt/evening-club/releases/<commit>` | 按完整提交号保存程序与该版本的 `.venv`、Node 依赖 |
| `/opt/evening-club/current` | 当前程序版本的符号链接 |
| `/opt/evening-club/node` | 官方 Node.js Linux x64 发行包的解压目录 |
| `/opt/evening-club/shared/data` | `DATA_DIR`；星港进度文件 `starport-progress.json` |
| `/opt/evening-club/backups` | 服务器本地数据备份 |
| `/etc/systemd/system/evening-club.service` | 程序启动、权限和重启配置 |
| `/etc/nginx/sites-available/evening-club` | 当前网站入口，HTTPS 部分由 Certbot 管理 |
| `/usr/local/sbin/evening-club-backup` | 数据备份脚本 |
| `/etc/cron.d/evening-club-backup` | 每日备份计划 |

配置模板在 [`deploy/tencent/`](../deploy/tencent/)。SSH 私钥、登录信息、证书私钥、实际服务器 IP 和数据文件不进入仓库。连接服务器时使用本机单独配置的 SSH 入口，并核对主机指纹。

## 新服务器配置

以下步骤面向新机器；不要把初始化模板覆盖到已经由 Certbot 配好 HTTPS 的生产配置上。

1. 从 Ubuntu 软件源安装 `nginx certbot python3-certbot-nginx git curl python3-venv xz-utils`。从 [Node.js 官方发行目录](https://nodejs.org/dist/latest-v22.x/)下载 Node.js 22 Linux x64 包，按 `SHASUMS256.txt` 校验后解压至 `/opt/evening-club/node`，使其 `bin` 目录进入安装和运行环境的 `PATH`。
2. 建立无交互登录的系统用户 `eveningclub`、上述目录。程序文件由 root 管理且可被 `eveningclub` 读取；`shared/data` 由 `eveningclub` 写入。父目录需要给该用户所在组遍历权限。
3. 按下节将选定提交解压到版本目录，安装依赖并建立 `current` 链接。安装 `evening-club.service`，执行 `systemctl daemon-reload` 与 `systemctl enable --now evening-club`。
4. 将 `nginx-http.conf` 安装到网站配置目录，建立 `sites-enabled` 链接。若与默认站点冲突，先备份并移出默认站点链接。建立 `/var/www/acme`，运行 `nginx -t` 后重载 Nginx。
5. 仅对外开放所需网站端口 80 / 443；SSH 使用独立密钥。10000 和星港内部端口保持回环监听。Nginx 覆盖 `X-Forwarded-For` 为直连访客地址，应用设置 `TRUSTED_PROXY_HOPS=1`，不要套用 Render 的 `CLIENT_IP_HEADER=CF-Connecting-IP`。
6. 检查新 IP 上的 `/_health` 和双人联机，再修改 DNS：主域名 A 记录指向新 IP，`www` CNAME 指向主域名。保留无关子域名记录。修改解析可能需要账号持有人完成腾讯云身份验证。
7. DNS 生效后执行证书签发命令，使用自己接收续期通知的邮箱：

   ```bash
   sudo certbot --nginx --redirect \
     -d lovecollection.online -d www.lovecollection.online \
     --email YOUR_EMAIL
   sudo systemctl list-timers certbot.timer
   ```

8. 安装备份脚本和计划：

   ```bash
   sudo install -m 750 deploy/tencent/backup.sh /usr/local/sbin/evening-club-backup
   sudo install -m 644 deploy/tencent/backup.cron /etc/cron.d/evening-club-backup
   sudo /usr/local/sbin/evening-club-backup
   ```

当前服务器时间为 Asia/Shanghai；计划在服务器当地时间每天 04:17 运行。备份按 `find -mtime +14` 清理，约保留两周。备份目录位于同一台服务器，不能替代异地备份；首次部署另存过一份本机副本，尚未配置持续的异地备份任务。

## 更新应用

选择已经通过 CI 的完整提交号。推送代码不会自动重启线上服务；更新和回滚都会清空进行中的房间，应选择无人游玩时操作。以下是维护步骤，按检查结果逐步执行。

在可信本机检查提交并打包：

```bash
git fetch origin main
commit=$(git rev-parse origin/main)
git archive --format=tar.gz -o /tmp/evening-club-source.tar.gz "$commit"
scp /tmp/evening-club-source.tar.gz YOUR_SSH_HOST:/tmp/evening-club-source.tar.gz
```

在服务器填写同一个完整提交号；使用新目录，已有同名目录时先检查，不覆盖：

```bash
commit=FULL_COMMIT_SHA
release="/opt/evening-club/releases/$commit"
test ! -e "$release" || exit 1
sudo install -d -m 755 "$release"
sudo tar -xzf /tmp/evening-club-source.tar.gz -C "$release"
sudo python3 -m venv "$release/.venv"
sudo "$release/.venv/bin/pip" install -r "$release/requirements.txt"
sudo env PATH=/opt/evening-club/node/bin:/usr/bin:/bin \
  /opt/evening-club/node/bin/npm --prefix "$release/starport" ci --omit=dev --no-audit --no-fund
```

先在独立回环端口试跑候选版本，使用单独的数据目录，不碰生产进度：

```bash
testdata=$(sudo -u eveningclub mktemp -d /tmp/evening-club-check.XXXXXX)
sudo -u eveningclub env PATH=/opt/evening-club/node/bin:/usr/bin:/bin \
  DATA_DIR="$testdata" "$release/.venv/bin/python" "$release/start.py" \
  --bind 127.0.0.1 --port 18780
```

另一个终端检查 `curl -f http://127.0.0.1:18780/_health`。候选服务检查结束后按 Ctrl+C 停止；确认其退出，再发布：

```bash
previous=$(readlink -f /opt/evening-club/current)
sudo /usr/local/sbin/evening-club-backup
sudo ln -s "$release" /opt/evening-club/current.next
sudo mv -Tf /opt/evening-club/current.next /opt/evening-club/current
sudo systemctl restart evening-club
curl --retry 10 --retry-connrefused --retry-delay 1 -f http://127.0.0.1:10000/_health
curl -f https://lovecollection.online/_health
```

应用健康检查会等待星港子进程可用；还需用两个客户端验证入房、邀请、开局、同步和重连。检查失败时保留日志，回滚到发布前记录的 `$previous`：

```bash
sudo ln -s "$previous" /opt/evening-club/current.rollback
sudo mv -Tf /opt/evening-club/current.rollback /opt/evening-club/current
sudo systemctl restart evening-club
curl --retry 10 --retry-connrefused --retry-delay 1 -f http://127.0.0.1:10000/_health
```

程序回滚不会恢复数据文件。未来若修改进度格式，要同时说明旧版本兼容性；不要用旧备份无条件覆盖最新进度。

## 数据和访客身份

| 数据 | 保存方式和边界 |
| --- | --- |
| 进行中的牌桌、房间、座位 | 服务内存；重启、发布后清空 |
| 星港个人通关进度 | 服务器 `DATA_DIR/starport-progress.json`；独立于版本目录保存 |
| 匿名访客 ID | 浏览器通过 `crypto.getRandomValues` 生成 16 字节随机值，编码为 32 位十六进制，保存为 `localStorage['club-id']` |
| 对弈游戏恢复座位 | 使用 `club-id` 作为 token；原房间存在时可恢复 |
| 星港恢复座位 | 另有服务器签发的座位 token，本地保存为 `starport-seat` |
| UNO | 当前界面按房间重新入座，没有复用 `club-id` 的座位恢复机制 |

匿名 ID 代表一个浏览器存储环境，不是账号或硬件身份。同一来源的多个标签页共享它；换浏览器、换 Profile、清除数据或新无痕会话会改变身份。主域名与 `www` 的存储相互独立，建议始终从主域名进入。换网络不改变 ID；访客 IP 另用于防刷限额，不用于保存个人进度。当前没有跨设备同步和找回匿名身份功能。

## 检查和故障定位

```bash
sudo systemctl status evening-club nginx
sudo journalctl -u evening-club -n 100 --no-pager
sudo tail -n 50 /var/log/nginx/error.log
sudo nginx -t
sudo certbot certificates
df -h /
```

- 页面可打开但无法联机：检查 `/ws/table`、`/ws/uno`、`/ws/starport` 是否成功升级为 WebSocket，以及 Nginx 的 Host、Upgrade、Connection 和超时配置。
- 访问新域名仍看到旧站：查询权威 DNS 与当地缓存，确认主域名和 `www` 都已切换。此次记录 TTL 为 600 秒，缓存实际更新时间由解析网络决定。
- 签发证书失败：检查域名解析、80 端口及校验日志。首次签发曾遇到一个境外二次校验节点连接超时，重试后成功；持续失败时查明原因，不连续盲目重试。
- 恢复数据：先停止应用并备份现有数据，把选定备份解压到暂存目录，核对文件内容和归属后替换，再启动应用；恢复会覆盖备份之后的通关记录。

2026-11-08 已通过线上 17 款游戏的自动化双客户端检查，包括邀请、开局、状态同步、房间隔离、重连、星港中继和同源限制；主域名与 `www` 的 TLS 校验通过。真实两台手机、不同运营商的体验仍需要实机验证。

外网 Python 测试客户端在收到正确的 `4001` 座位转移关闭帧后，曾在回复关闭时报告连接已断开；服务器内的原始 HTTPS 检查通过。后续复查应同时查看收到的关闭帧和客户端异常，不能仅凭最终 `close_code` 判断是服务端发送了错误代码。

## 备案信息

域名在腾讯云账号内的备案状态正常，登记的服务名称仍为旧项目“家务打卡记录”，尚未变更为当前网站内容。正式资料变更由账号持有人在备案控制台办理，不能把服务器部署完成等同于备案内容已更新。参考腾讯云的[变更备案说明](https://cloud.tencent.com/document/product/243/19617)。

以上状态来自当日服务器配置、DNS 权威查询、代码与线上协议检查；后续运维以实际服务器和当前代码为准。
