<p align="center">
  <img alt="Ifrit logo" src="docs/static/img/ifrit.svg" height="160" width="160">
</p>

<h1 align="center">Ifrit Timesheet Tracker</h1>

<p align="center">
  一款现代化的开源工时跟踪与报表应用，由您自己托管。
</p>

<p align="center">
  <a href="https://github.com/tonyp7/ifrit/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/tonyp7/ifrit/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://htmlpreview.github.io/?https://github.com/tonyp7/ifrit/blob/python-coverage-comment-action-data/htmlcov/index.html"><img alt="Backend test coverage" src="https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Ftonyp7%2Fifrit%2Fpython-coverage-comment-action-data%2Fendpoint.json"></a>
  <a href="https://github.com/tonyp7/ifrit/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/tonyp7/ifrit"></a>
  <a href="LICENSE"><img alt="License: Apache 2.0" src="https://img.shields.io/github/license/tonyp7/ifrit"></a>
  <a href="https://github.com/tonyp7/ifrit/pkgs/container/ifrit"><img alt="Container image" src="https://img.shields.io/badge/ghcr.io-tonyp7%2Fifrit-blue?logo=docker&logoColor=white"></a>
</p>

<p align="center">
  <a href="https://docs.ifrit.day/">文档（英文）</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="CHANGELOG.md">更新日志（英文）</a> ·
  <a href="https://github.com/tonyp7/ifrit/issues">报告问题</a>
</p>

<p align="center">
  <a href="README.md">English</a> · 简体中文
</p>

---

Ifrit 面向代理机构、咨询公司，以及一切以工时为业务核心的公司：员工把工时记在各个项目上，经理审核并锁定，最后导出为报表。

## 功能

- **工时记录。** 按周或按月填写的响应式工时表，自动保存。在电脑和手机上的使用方式相同。
- **项目。** 项目包含服务项目（数量、单位和单价），每个服务项目可分配顾问，并可为项目附上支持文档。
- **管理。** 经理审核其项目中所有人的工时，进行更正，并在某个周期最终确定后将其锁定。
- **公司。** 供应商和客户只需登记一次，包括其标识和地址，即可在多个项目中重复使用。
- **报表。** 按顾问、项目、服务项目或状态筛选，然后导出为 PDF、Excel 或 CSV。
- **开票。** 财务可根据已记录的工时或计费里程碑，为工时计费项目和固定价格项目准备发票，添加税费，按独立的编号规则开具和作废发票，并通过可自行编辑的模板生成 PDF。
- **角色。** 顾问、经理、财务和管理员各自只看到所需的页面。
- **浅色和深色主题**，默认跟随您的系统。
- **提供英语、法语和简体中文界面。** Ifrit 默认使用浏览器的语言，您也可以在个人资料菜单中切换。
- **自行托管。** 一个容器镜像加上 PostgreSQL，用 Docker Compose 启动。数据库迁移会在容器启动时自动运行。

## 快速开始

您需要安装带有 Compose 插件的 [Docker](https://docs.docker.com/get-docker/)。下面的命令会在您自己的机器上启动一个用完即弃的实例，无需任何配置：

```shell
curl -O https://raw.githubusercontent.com/tonyp7/ifrit/main/docker/examples/local-docker-compose/docker-compose.yml
docker compose up -d
docker compose exec app python -m scripts.seed_admin
```

然后打开 <http://localhost:8081>，使用以下账号登录：

| 邮箱 | 密码 |
|---|---|
| `admin@ifrit.local` | `ifrit-local-trial` |

这套配置仅用于试用 Ifrit：只能从您自己的机器访问，使用明文 HTTP，并且使用公开的默认密钥。若要正式运行 Ifrit，请在您自己的域名上通过 HTTPS 提供服务，并按照下面的自行托管指南操作。

## 文档

完整文档位于 **[docs.ifrit.day](https://docs.ifrit.day/)**。文档目前只有英文版，下面的链接都指向英文页面。

| 我想要… | 阅读 |
|---|---|
| 为我的公司运行 Ifrit | [自行托管](https://docs.ifrit.day/self-hosting/) |
| 查阅所有设置 | [配置](https://docs.ifrit.day/configuration/) |
| 把 Ifrit 放在反向代理之后 | [反向代理](https://docs.ifrit.day/reverse-proxy/) |
| 不用 Docker 运行，用于开发 | [本地运行](https://docs.ifrit.day/local-run/) |
| 学习如何使用 | [用户指南](https://docs.ifrit.day/guide/roles/) |

用于生产环境的现成 Compose 和 nginx 文件位于 [`docker/examples`](docker/examples/)。

## 版本发布

Ifrit 遵循[语义化版本](https://semver.org)。每个版本对应一个 `vX.Y.Z` 标签，并向 GitHub Container Registry 发布一个容器镜像：

```text
ghcr.io/tonyp7/ifrit:2.5.0     an exact release (recommended for production)
ghcr.io/tonyp7/ifrit:2.5       the latest patch of 2.5
ghcr.io/tonyp7/ifrit:latest    the current state of main (not for production)
```

上面三行依次表示：确切的版本（推荐用于生产环境）、该次版本的最新补丁、`main` 的当前状态（不适用于生产环境）。

升级前请阅读[更新日志](CHANGELOG.md)（英文），并先做好备份。升级方法见[自行托管指南](https://docs.ifrit.day/self-hosting/)。

## 技术栈

- **后端：** Python、[FastAPI](https://fastapi.tiangolo.com)、SQLAlchemy 和 Alembic
- **前端：** React 和 TypeScript，使用 [Vite](https://vite.dev) 构建，界面基于 [shadcn/ui](https://ui.shadcn.com) 和 Tailwind CSS
- **数据库：** PostgreSQL
- **PDF 发票：** [LibreOffice](https://www.libreoffice.org)（无界面模式）把可编辑的模板转换为 PDF
- **部署：** 单个多阶段 Docker 镜像，由 nginx 提供网页界面

## 参与贡献

欢迎在[问题跟踪器](https://github.com/tonyp7/ifrit/issues)中提交错误报告和想法。

要参与代码开发，请按照[本地运行](https://docs.ifrit.day/local-run/)（英文）在您的机器上运行后端和前端。请从分支发起拉取请求，并先确保测试和代码检查通过：

```shell
cd backend  && uv run pytest -q && uv run ruff check .
cd frontend && pnpm test && pnpm lint
```

## 许可证

Ifrit 以 [Apache License 2.0](LICENSE) 发布。需要署名的第三方素材（例如应用图标）及其作者和许可证，列在 [ACKNOWLEDGMENTS](ACKNOWLEDGMENTS) 中。
