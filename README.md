# CloudPilot

独立于 MoviePilot 的网盘资源转存自动化系统。

## 主流程

```text
搜索 → PanSou → 网盘分享结果 → 一键转存 → 自己的网盘目录
```

## 已包含

- Docker Compose 部署
- 手机端网页
- 多用户登录
- PanSou 搜索源
- CloudResult 标准化
- CloudSaveTask 转存任务
- 订阅框架
- 推送 Webhook 框架
- 夸克 / 115 / 阿里 / UC / 百度 / 天翼 / PikPak / 迅雷 / 移动云盘 / 123云盘适配器骨架

## 启动

```bash
docker compose up -d --build
```

访问：

```text
http://你的NAS-IP:8899
```

默认账号：

```text
admin
admin123
```

## 当前限制

真实网盘转存接口尚未补全，位置：

```text
backend/app/cloud.py
```

当前点击“一键转存”会创建任务并调用适配器，适配器返回“真实转存接口待接入”。
