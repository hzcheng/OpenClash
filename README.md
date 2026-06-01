# OpenClash Mihomo 网关

本仓库构建一个自定义 `mihomo` 镜像，内置 `metacubexd` 面板，并通过启动脚本在每次容器启动时从订阅 URL 加上部署侧配置覆盖，动态生成运行时 `config.yaml`。

## 这个部署做了什么

- 在内网机器上运行 `mihomo`。
- 对外暴露一个共享混合代理端口，供宿主机、Docker 容器、LAN 设备和 Tailnet 设备使用。
- 控制面板直接通过控制器端口访问，无需经过公网代理。
- 每次容器启动时从订阅重新生成运行时 `config.yaml`。

## 必填 `.env` 变量

在 `.env` 中设置（默认值参见 `.env.example`）：

- `OPENCLASH_SUBSCRIPTION_URL`：Clash 兼容的订阅链接。
- `OPENCLASH_MIXED_PORT`：供宿主机、容器、LAN 和 Tailnet 共享的混合代理端口。
- `OPENCLASH_CONTROLLER_PORT`：控制器/UI 端口，面板通过此端口直接访问。
- `OPENCLASH_LOG_LEVEL`：`mihomo` 日志级别。
- `OPENCLASH_UI_PATH`：面板的 URL 前缀路径（保持 `/openclash/`）。
- `OPENCLASH_UI_DIR`：容器内 UI 静态资源路径。
- `OPENCLASH_STATE_DIR`：容器内运行时状态目录。
- `OPENCLASH_AUTO_UPDATE_UI`：文档占位，无实际效果（UI 资源在构建时已打入镜像）。
- `OPENCLASH_BUILD_ALPINE_REPO`：可选，构建时 Alpine 镜像源根路径，大陆环境适用。
- `OPENCLASH_BUILD_METACUBEXD_URL`：可选，构建时 UI 压缩包 URL 覆盖。

典型本地配置：

```dotenv
OPENCLASH_SUBSCRIPTION_URL=https://example.com/subscription.yaml
OPENCLASH_MIXED_PORT=9981
OPENCLASH_CONTROLLER_PORT=9097
OPENCLASH_LOG_LEVEL=warning
OPENCLASH_UI_PATH=/openclash/
OPENCLASH_UI_DIR=/root/.config/mihomo/ui
OPENCLASH_STATE_DIR=/root/.config/mihomo
OPENCLASH_AUTO_UPDATE_UI=false
```

## 代理使用方式

混合代理端口现已在所有网卡上监听。

示例：

- HTTP 代理：`http://127.0.0.1:9981`
- HTTPS 代理：`http://127.0.0.1:9981`
- SOCKS 兼容客户端（混合模式）：`127.0.0.1:9981`

各场景接入地址：

- 宿主机：`127.0.0.1:${OPENCLASH_MIXED_PORT}`
- 同机 Docker 容器：`http://host.docker.internal:${OPENCLASH_MIXED_PORT}`
- LAN 设备：`http://<内网主机 LAN IP>:${OPENCLASH_MIXED_PORT}`
- Tailnet 设备：`http://100.101.7.100:${OPENCLASH_MIXED_PORT}`

该代理出口不需要用户名/密码认证，LAN 或 Tailnet 内能访问到本机的设备均可直接使用。

`mihomo` 要求外部 UI 路径位于其安全目录下，因此默认 state/UI 路径均使用容器内的 `/root/.config/mihomo`。

## 控制面板

面板直接通过控制器端口访问，无需公网代理：

- 宿主机：`http://127.0.0.1:${OPENCLASH_CONTROLLER_PORT}/ui/`
- LAN 设备：`http://<内网主机 LAN IP>:${OPENCLASH_CONTROLLER_PORT}/ui/`
- Tailnet 设备：`http://100.101.7.100:${OPENCLASH_CONTROLLER_PORT}/ui/`

首次打开时，`metacubexd` 可能提示配置后端地址，填入对应的 `http://<IP>:${OPENCLASH_CONTROLLER_PORT}` 即可。

## 启动

```bash
cd /Projects/Repos/OpenClash
cp .env.example .env
docker compose --env-file .env config
docker compose --env-file .env build
docker compose --env-file .env up -d --remove-orphans
```

如在大陆构建且官方上游较慢，可在运行 `docker compose build` 前在 `.env` 中覆盖两个构建时源 URL。

## 日常操作

### 刷新订阅和运行时配置

`config.yaml` 在容器启动时自动重新生成。拉取最新订阅并重建配置：

```bash
cd /Projects/Repos/OpenClash
docker compose --env-file .env restart
```

如果修改了 `Dockerfile`、`bootstrap-openclash.sh` 等构建相关文件：

```bash
cd /Projects/Repos/OpenClash
docker compose --env-file .env build
docker compose --env-file .env up -d --force-recreate --remove-orphans
```

### 查看运行时状态

```bash
docker logs --tail 200 openclash
docker exec openclash sh -c 'sed -n "1,80p" /root/.config/mihomo/config.yaml'
docker exec openclash sh -c 'cat /root/.config/mihomo/ui/config.js'
```

### 停止/启动服务

```bash
cd /Projects/Repos/OpenClash
docker compose --env-file .env stop
docker compose --env-file .env start
```

## 验证

从内网宿主机：

```bash
docker compose --env-file .env ps
curl -sS -D - -o /tmp/openclash-ui.html http://127.0.0.1:${OPENCLASH_CONTROLLER_PORT}/ui/ | sed -n '1,20p'
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:${OPENCLASH_MIXED_PORT} || true
```

预期：

- `openclash` 容器状态为 `Up`
- `/${OPENCLASH_CONTROLLER_PORT}/ui/` 返回 `200`
- 宿主机可访问共享代理端口

从 Tailnet 可达的其他机器：

```bash
curl --noproxy '*' -sS -D - -o /tmp/openclash-tailnet-ui.html http://100.101.7.100:${OPENCLASH_CONTROLLER_PORT}/ui/ | sed -n '1,20p'
curl --noproxy '*' -sS -o /dev/null -w '%{http_code}\n' http://100.101.7.100:${OPENCLASH_MIXED_PORT} || true
```

预期：

- 控制器/UI 路径返回 `200`
- 混合代理端口在 Tailnet 地址上有响应

从同机 Docker 容器：

```bash
docker exec DevBox-devbox sh -lc 'env -u http_proxy -u https_proxy -u all_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY curl --noproxy "*" -sS -o /dev/null -w "%{http_code}\n" http://host.docker.internal:9981'
```

预期：

- 容器可通过 `host.docker.internal` 访问共享代理

从公网：

```bash
curl -k -I https://gate.teraai.cn/openclash/
curl -k -I https://gate.teraai.cn/openclash/ui/
```

预期：

- `/openclash/` 返回 `302` 跳转到 `/openclash/ui/`
- `/openclash/ui/` 在未提供网关认证时返回 `401`

## OpenAI 分流

OpenAI 流量被引导到由订阅中新加坡节点组成的 `url-test` 代理分组。每次容器重启，渲染器会向运行时配置注入三项内容：

- `rule-providers.openai`：拉取 `blackmatrix7` 的 OpenAI 规则列表（jsdelivr 镜像，每 24 小时刷新一次）
- `OpenAI` 代理分组（`type: url-test`）：成员为订阅中名称匹配 `OPENCLASH_OPENAI_REGION_REGEX` 的节点
- 最高优先级规则 `RULE-SET,openai,OpenAI`

默认只使用新加坡节点。如需同时包含日本节点：

```dotenv
OPENCLASH_OPENAI_REGION_REGEX=(?i)(🇸🇬|🇯🇵|SG|JP|Singapore|Japan|新加坡|日本|东京|狮城|Tokyo)
```

默认健康检查 URL 为 `https://chat.openai.com/cdn-cgi/trace`，能真实反映 OpenAI 的可达性。如果节点服务商对 Cloudflare trace 探测有频率限制，可切换为更宽松的 Google 探测地址：

```dotenv
OPENCLASH_OPENAI_HEALTHCHECK_URL=https://www.gstatic.com/generate_204
```

如果某次订阅刷新后没有节点匹配正则，渲染器会报错退出，容器拒绝启动——不会静默降级为 DIRECT。请在上游重命名节点，或放宽正则表达式。

## 大陆网络说明

本部署包含两项针对大陆网络环境的加固：

- 构建时可通过 `OPENCLASH_BUILD_ALPINE_REPO` 指定镜像源
- 生成的 `mihomo` 配置将 `geox-url` 固定指向 `testingcf.jsdelivr.net`，避免从 GitHub Release 拉取 GEO/MMDB 时卡住

如果启动日志长时间出现 `Can't find MMDB, start download`，先检查出站连通性：

```bash
docker exec openclash sh -c 'curl -I --max-time 20 https://testingcf.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@release/country.mmdb'
```

## 常见问题

- 容器反复重启并出现 `SAFE_PATHS` 错误：确认 `OPENCLASH_STATE_DIR` 和 `OPENCLASH_UI_DIR` 均在 `/root/.config/mihomo` 下。
- 面板能打开但无法连接后端：确认 `/root/.config/mihomo/ui/config.js` 中包含 `defaultBackendURL: '/openclash/'`。
- Tailnet 内 `/openclash/ui/` 可访问但公网不行：检查 `NestGate` 路由渲染和网关认证配置。
- 代理对 LAN、Tailnet 或容器意外不可达：检查 compose 中 `OPENCLASH_MIXED_PORT` 的端口绑定，确认不再绑定到 `127.0.0.1`。
- 更新订阅后配置未生效：重启或重建容器，让 bootstrap 流程重新生成 `config.yaml`。

## 关键文件

- `docker-compose.yml`：运行时端口、重启策略和状态卷
- `Dockerfile`：含 `mihomo`、bootstrap 工具和 `metacubexd` 的自定义镜像
- `scripts/bootstrap-openclash.sh`：启动编排、UI 同步和配置生成
- `scripts/render_openclash_config.py`：部署侧配置覆盖逻辑
- `.env.example`：部署契约
- `README.md`：本服务的运维说明
