# CTM电信 Home Assistant 集成（一体化）

这是一个基于 [ChinaTelecomMonitor](https://github.com/Cp0204/ChinaTelecomMonitor) 核心逻辑，并**直接集成到 Home Assistant** 的中国电信话费、通话、流量套餐用量监控解决方案。

**本项目已将数据获取功能与 Home Assistant 集成合二为一，不再需要单独部署 `ChinaTelecomMonitor` 的 API 服务。**

## 特性

* **一体化部署：** 无需额外的 Docker API 服务，直接在 Home Assistant 中配置和运行。
* **实时数据：** 监控话费余额、本月消费、流量用量（通用/专用）、通话时长等关键数据。
* **流量与通话使用率：** 新增流量已用百分比和通话已用百分比传感器，更直观地了解使用情况。
* **自动处理登录与 Token：** 集成内部处理电信账号的登录、Token 刷新和过期重试机制。
* **Home Assistant 原生体验：** 作为 HACS 集成或自定义组件安装，提供友好的配置界面。

## 效果展示



UI配置框：

![aaced0ce58f97284af31be2dddcb5a5](https://github.com/user-attachments/assets/a7549c09-f7db-4b3c-8934-104189713018)


实际效果：
![7809c0446e278c6a4f354c6b33c4b80](https://github.com/user-attachments/assets/0bac6024-cf65-494d-b9e7-03247dcd9ec2)


## 如何使用本集成

### ✅ 方法一：通过 HACS 安装（推荐）

1.  打开 Home Assistant 左侧菜单，点击 **HACS**。
2.  进入右上角菜单 → 选择 **“自定义存储库”**。
3.  填入仓库地址：`https://github.com/hlhk2017/ChinaTelecomMonitor-Homeassistant-Integration`
4.  类型选择 **集成 (Integration)**，点击添加。
5.  返回 HACS 主界面，搜索并安装 **“CTM电信”**。
6.  安装完成后，前往 **“设置 → 设备与服务 → 添加集成”**。
7.  搜索 **CTM电信**，点击添加并完成配置（只需输入手机号和密码）。

[![快速通过 HACS 链接安装](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=hlhk2017&repository=ChinaTelecomMonitor-Homeassistant-Integration&category=integration)

### 方法二：手动安装

1.  下载本项目源代码。
2.  将整个 `custom_components/china_telecom` 目录复制到 Home Assistant 的配置路径下：
    `[你的 Home Assistant 配置目录]/custom_components/china_telecom`
3.  **重启 Home Assistant。** (重要：不是重新加载集成，是完整重启 Home Assistant 服务)
4.  前往 **“设置 → 设备与服务 → 添加集成”**。
5.  搜索 **CTM电信**，点击添加并完成配置。

## 感谢

本项目核心数据获取逻辑大量参考了 [Cp0204/ChinaTelecomMonitor](https://github.com/Cp0204/ChinaTelecomMonitor) 项目的代码，在此表示衷心感谢！
