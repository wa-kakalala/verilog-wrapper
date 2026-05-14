# Verilog-Wrapper

> 一款为数字IC设计和FPGA开发者打造的可视化连线与顶层封装工具。

## 项目简介

在传统的SoC开发或复杂模块集成中，手动编写顶层例化代码往往伴随着繁琐的端口映射、位宽对齐检查以及容易出错的连线定义。本项目通过可视化的节点图（Node-based Graph）解决这一痛点，让硬件工程师能够像连原理图一样，直观、安全、高效地完成模块互联，并一键生成无错的 `top_design.v` 顶层文件。

## 技术栈

| 层级   | 技术                                 |
| ------ | ------------------------------------ |
| 前端   | Vue 3 + Vue Flow + Vite              |
| 后端   | Python FastAPI + pyverilog            |
| 端口   | 前端 :5173 / 后端 :8000               |

## 环境要求

- **Python** >= 3.10
- **Node.js** >= 22.x（自带 npm）

## 快速启动

### 方式一：一键启动（推荐）

双击项目根目录下的 `start.bat`，即可同时启动前端和后端。

### 方式二：分别启动

打开两个终端，分别执行：

**启动后端（FastAPI，端口 8000）：**

```bash
cd backend
python verilog-editor.py
```

**启动前端（Vite 开发服务器，端口 5173）：**

```bash
cd verilog-editor
npx vite --host
```

### 访问地址

启动后在浏览器中打开：**http://localhost:5173**

## 依赖安装

首次运行前需要安装依赖：

**后端（Python）：**

```bash
cd backend
pip install ply==3.11 fastapi uvicorn pydantic python-multipart
```

**前端（Node.js）：**

```bash
cd verilog-editor
npm install
```

## 项目结构

```
verilog-wrapper/
├── start.bat                     # 一键启动脚本
├── readme.md                     # 项目文档
├── .gitignore
├── backend/                      # Python 后端
│   ├── verilog-editor.py         # FastAPI 主程序入口
│   ├── requirements.txt          # Python 依赖
│   ├── example.v                 # 示例 Verilog 文件
│   └── pyverilog/                # Verilog 解析库（本地捆绑）
│       └── vparser/              # 词法/语法分析器
├── verilog-editor/               # Vue 前端
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── App.vue               # 主界面与核心逻辑
│       ├── main.ts               # 入口
│       └── components/
│           ├── VerilogNode.vue   # 模块节点组件
│           ├── TopIONode.vue     # 顶层IO节点组件
│           └── WaypointNode.vue  # 连线拐点组件
└── pic/                          # 图片资源
```

## 核心功能

### 模块互联与校验

- **智能连线**：从模块输出端口拖动到输入端口建立连接，自动创建 smoothstep 型连线
- **多重驱动拦截**：一个输入端口只能连接一个信号源，自动阻止重复驱动
- **位宽校验**：连接时严格检查输出端口位宽与输入端口位宽是否匹配，不匹配时阻止并提示
- **总线识别**：自动区分总线与单根信号，总线以加粗和动画显示

### 内置IP模块

左侧 IP Catalog 面板提供常用内置模块，点击即可添加到画布：

| 模块     | 功能                         |
| -------- | ---------------------------- |
| Convert  | 位宽转换 / 信号切片           |
| Constant | 常量信号源，可配置位宽和值      |
| Concat   | 多信号位拼接                  |
| NOT      | 按位取反，位宽可配置           |

### 顶层参数配置

工具栏下方的 Params 栏支持配置顶层模块的 parameter 参数（如 `WIDTH = 16`），生成的 RTL 代码将使用参数名表达式而非字面值。

### 连线编辑

- **Waypoint 拐点**：双击连线在下半段插入可拖拽的拐点节点，支持自定义走线路径
- **线段自愈**：删除拐点后自动拉直连线，底层网表逻辑同步更新
- **一键断开**：右键端口选择"断开端口连接"，自动清理该端口的所有连接并移除相关拐点
- **边选中高亮**：单击选中连线时显示橙色发光高亮效果

### 顶层IO

- **标记为Top IO**：右键端口选择"标记为 Top 顶层 IO"，自动在模块外侧生成顶层IO节点
- **方向区分**：
  - 输入 Top IO（蓝色）右侧连接，信号流向模块输入端口
  - 输出 Top IO（红色）左侧连接，信号从模块输出端口流出
- **连线颜色区分**：输入 Top IO 连线为蓝色，输出 Top IO 连线为红色，与内部连线明显区分
- **同步删除**：删除 Top IO 连线时，对应的 Top IO 节点自动同步删除

### NC（悬空标记）

- 右键端口选择 "Mark as NC"，端口变半透明+删除线
- NC 端口不能被连接
- 生成代码时自动跳过 NC 端口

### 连线信号命名

- 模块间连线：`from_起始模块_to_目标模块_信号名`
- 顶层输入端：`I_端口名`
- 顶层输出端：`O_端口名`

### 模块操作

- **拖拽移动**：所有节点支持拖拽移动，连线自动跟随
- **参数编辑**：双击模块参数区域弹出编辑框，修改位宽等参数后自动重算端口宽度
- **模块复制**：选中模块后 `Ctrl+C` 复制，`Ctrl+V` 粘贴，新实例自动剥离原有连线状态
- **删除**：选中节点后按 `Delete` 键删除，同时清理所有关联连线

### 工程管理

- **上传解析**：通过工具栏上传 `.v` 文件，后端调用 pyverilog 解析模块端口信息并返回 JSON
- **保存/加载**：工程数据自动保存到 localStorage，刷新页面不丢失
- **导出/导入 JSON**：支持将当前工程导出为 JSON 文件或从 JSON 文件导入

### 代码生成

- **生成Top模块**：基于画布上的网表连接关系，一键生成 Verilog 顶层例化代码
- **内置模块展开**：Constant → `assign ... = N'dV;`、Convert → 位选、Concat → 拼接、NOT → 取反
- **参数支持**：顶层 parameter 自动生成为 `module top_design #(parameter WIDTH = 16)`
- **代码弹窗**：生成的代码在弹窗中展示，支持 Copy（复制）和 Save（下载 .v 文件）

## 操作快捷键

| 快捷键          | 功能                    |
| --------------- | ----------------------- |
| Delete          | 删除选中节点/连线        |
| Ctrl+C          | 复制选中模块             |
| Ctrl+V          | 粘贴模块                 |
| 双击模块参数     | 编辑模块参数             |
| 双击连线         | 插入拐点（Waypoint）     |
| 右键端口         | 打开端口操作菜单         |

## 常见问题

**Q: 启动后端时卡在 "Generating LALR tables"？**

A: 这是 pyverilog 在生成语法分析表，属于正常现象，等待几秒即可完成。

**Q: 端口被占用怎么办？**

A: 先关闭占用端口的进程，或修改 `verilog-editor.py` 中的端口号（默认 8000）和 `vite.config.ts` 中的 Vite 端口配置。

**Q: PowerShell 执行 npm 报错"无法加载文件 npm.ps1"？**

A: 请使用 CMD 终端执行，或在 PowerShell 中用 `cmd /c` 前缀运行命令。