# BigSimWorld

[English](./README-en.md) | 简体中文

## 概述
BigSimWorld是一个模拟项目，使用Python作为后端和Vue.js作为前端，旨在模拟大规模环境和交互。

## 特性
- 使用Vue.js进行交互式模拟可视化
- 由Python后端管理的数据处理和API端点
- 使用SQLite3进行轻量级数据库管理
- 使用Redis进行缓存和实时数据处理

## 项目结构
```bash
# 项目目录结构

.
├── app/
│   ├── api/                # API端点
│   ├── core/               # 核心功能（生成、模拟、统计）
│   ├── models/             # 数据库模型和处理
│   ├── schemas/            # API的JSON架构
│   ├── services/           # 数据处理服务
│   └── utils/              # 工具函数
├── LICENSE                  # 项目许可证
├── logs/                   # 日志文件
├── run.py                  # 运行模拟的主脚本
└── web/
    ├── package.json
    ├── src/
    │   ├── App.vue
    │   ├── components/      # 可重用的Vue组件
    │   ├── plugins/         # Vue插件
    │   ├── router/          # Vue路由配置
    │   └── views/           # 应用程序的主视图
    └── vite.config.mjs      # Vite配置
```

## 安装说明

### 后端（Python）
- 需要Python 3.11及以上版本。
1. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
2. 运行后端：
   ```bash
   python run.py
   ```

### 前端（Vue.js）
1. 进入`web`目录：
   ```bash
   cd web
   ```
2. 安装前端依赖（需要Node.js 20及以上版本）：
   ```bash
   pnpm install
   ```
3. 启动前端：
   ```bash
   pnpm dev
   ```

## API
该项目提供RESTful端点供交互使用。示例端点：
- `/api/v1/subscribe/get-client-id`：获取用户的唯一客户端ID。
- `/api/v1/subscribe/notify-connection`：通知服务器客户端已连接。
- `/api/v1/subscribe/unsubscribe/<client_id>`：从模拟中取消订阅客户端。

## 许可证
该项目采用MIT许可证。