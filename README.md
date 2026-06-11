# CloudPilot

独立于 MoviePilot 的网盘资源搜索、识别、分类和转存自动化系统。

## 主流程

```text
搜索 → PanSou → 网盘分享结果 → 一键转存 → 自己的网盘目录
```

## 已包含

- Docker Compose 部署
- 手机端网页
- 多用户登录
- PanSou 搜索源
- TMDB 媒体识别、推荐和详情
- 影视资源分类
- CloudResult 标准化
- CloudSaveTask 转存任务
- 订阅框架
- 推送 Webhook 框架
- 夸克真实转存
- 115 / 阿里 / UC / 百度 / 天翼 / PikPak / 迅雷 / 移动云盘 / 123云盘适配器骨架

## 启动

复制环境变量示例并修改密码和密钥：

```bash
cp .env.example .env
```

至少需要修改：

```text
CLOUDPILOT_SECRET_KEY
CLOUDPILOT_ADMIN_PASSWORD
```

如果想在 NAS 上本地构建镜像，然后启动：

```bash
docker compose up -d --build
```

也可以直接使用 GitHub Container Registry 发布的镜像：

```bash
docker pull ghcr.io/denghuohhh/cloudpilot:latest
docker compose -f docker-compose.image.yml up -d
```

访问：

```text
http://你的 NAS-IP:8899
```

管理员账号：

```text
CLOUDPILOT_ADMIN_USER
CLOUDPILOT_ADMIN_PASSWORD
```

## 当前限制

除夸克外，其它网盘真实转存接口尚未补全，位置：

```text
backend/app/cloud.py
```

夸克需要在设置页配置 Cookie 和目标目录 FID。其它网盘当前点击“一键转存”会创建任务并调用适配器，适配器返回“真实转存接口待接入”。
