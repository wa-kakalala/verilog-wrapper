# 📦 Verilog-Wrapper

> readme暂时由AI生成，后续会修改。

![Vue3](https://img.shields.io/badge/Vue.js-3.0-green?logo=vue.js)
![VueFlow](https://img.shields.io/badge/Vue_Flow-Node_Based-blue)
![Verilog](https://img.shields.io/badge/Verilog-HDL-purple)

**Verilog_Wrapper** 是一款为数字 IC 设计和 FPGA 开发者打造的轻量级、可视化连线与顶层封装工具。

在传统的 SoC 开发或复杂模块集成中，手动编写顶层例化代码（Instantiation）往往伴随着繁琐的端口映射、位宽对齐检查以及容易出错的连线定义。本项目旨在通过可视化的节点图（Node-based Graph）解决这一痛点，让硬件工程师能够像连原理图一样，直观、安全、高效地完成模块互联，并一键生成无错的 `top.v` 顶层文件。

### ✨ 核心特性 (Key Features)

* **🔌 智能连线与校验 (Smart Connection):**
  * 自动拦截多重驱动（防止短路）。
  * 严格的端口位宽校验（防止 `[31:0]` 错连到 `[15:0]`）。
  * 区分单根信号与总线（总线加粗/高亮显示）。
* **✂️ 极客级布线交互 (Advanced Routing):**
  * **自由布线：** 双击连线生成可拖拽的拐点（Waypoint），支持强迫症级别的网表整理。
  * **线段自愈 (Line Healing)：** 删除拐点自动拉直连线，底层逻辑严密同步。
  * **一删全删：** 终极网表清理引擎，防止视觉连线与底层 JSON 数据脱节。
* **🛠 硬件思维的右键菜单:**
  * 一键将内部模块端口引出为 **Top IO**。
  * 快速断开当前端口的所有连接。
* **🚀 状态隔离的模块复用:**
  * 支持 `Ctrl+C` / `Ctrl+V` 快速复制模块实例，并自动深拷贝剥离原有连线状态，杜绝拷贝导致的网表逻辑污染。
* **📦 左侧 IP Catalog (模块库):**
  * 直观的左右分栏布局，极简侧边栏支持后续拖拽生成模块。