<template>
  <div class="verilog-module" :class="{ 'is-selected': selected }">
    <div class="module-header">
      <span class="module-name">{{ data.mdl_name }}</span>
    </div>

    <div 
      class="module-params" 
      v-if="data.params && data.params.length"
      @dblclick="openEditModal"
      title="双击修改参数"
    >
      <div v-for="p in data.params" :key="p.param_name" class="param-item">
        #({{ p.param_name }} = {{ p.param_value }})
      </div>
    </div>

    <div class="ports-container">
      <div class="ports-left">
        <div 
          v-for="port in data.in_ports" 
          :key="port.port_name" 
          class="port-row"
          :class="{ 'port-active': menuState && menuState.visible && menuState.port === port }"
          @contextmenu.prevent="onPortRightClick($event, port, 'in')"
        >
          <Handle type="target" :id="port.port_name" :position="Position.Left" class="custom-handle target-handle" />
          <span class="port-name">{{ port.port_name }}</span>
          <span class="port-width" v-if="port.left !== 0 || port.right !== 0">
            [{{ port.left }}:{{ port.right }}]
          </span>
        </div>
      </div>

      <div class="ports-right">
        <div 
          v-for="port in data.out_ports" 
          :key="port.port_name" 
          class="port-row right-align"
          :class="{ 'port-active': menuState && menuState.visible && menuState.port === port }"
          @contextmenu.prevent="onPortRightClick($event, port, 'out')"
        >
          <span class="port-width" v-if="port.left !== 0 || port.right !== 0">
            [{{ port.left }}:{{ port.right }}]
          </span>
          <span class="port-name">{{ port.port_name }}</span>
          <Handle type="source" :id="port.port_name" :position="Position.Right" class="custom-handle source-handle" />
        </div>
      </div>
    </div>

    <Teleport to="body">
      <div v-if="isEditing" class="modal-overlay" @click.self="closeModal">
        <div class="modal-content">
          <div class="modal-header">
            <h3>修改参数 - {{ data.mdl_name }}</h3>
          </div>
          
          <div class="modal-body">
            <div class="form-group" v-for="(p, index) in editParams" :key="index">
              <label :title="p.param_name">{{ p.param_name }}</label>
              <input v-model="p.param_value" type="text" />
            </div>
          </div>
          
          <div class="modal-footer">
            <button class="btn-cancel" @click="closeModal">取消</button>
            <button class="btn-primary" @click="saveParams">保存修改</button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div 
        v-if="menuState && menuState.visible" 
        class="port-context-menu" 
        :style="{ top: menuState.y + 'px', left: menuState.x + 'px' }"
        @click.stop
      >
        <div class="menu-header">
          {{ menuState.port.port_name }} 
          <span class="menu-port-dir">({{ menuState.type === 'in' ? 'Input' : 'Output' }})</span>
        </div>
        <div class="menu-item" @click="handleMakeTopIO">
          📌 标记为 Top 顶层 IO
        </div>
        <div class="menu-item text-danger" @click="handleDisconnect">
          ✂️ 断开端口连接
        </div>
      </div>
    </Teleport>
  </div>
</template>


<script setup>
import { ref, onMounted, onUnmounted, inject } from 'vue' // 补充引入生命周期钩子
import { Handle, Position } from '@vue-flow/core'

const props = defineProps({ 
  id: String,
  selected: Boolean, 
  data: { type: Object, required: true } 
})

const isEditing = ref(false)
const editParams = ref([])

const openEditModal = () => {
  if (!props.data.params || props.data.params.length === 0) return
  editParams.value = JSON.parse(JSON.stringify(props.data.params))
  isEditing.value = true
}

const closeModal = () => {
  isEditing.value = false
}

// 表达式计算引擎
const evaluateExpression = (expr, paramsList) => {
  if (!expr) return 0
  let evalStr = String(expr)

  // 1. 将参数按名称长度降序排序 (非常重要：防止匹配 'N' 时错误替换了 'LOG_N' 中的 'N')
  const sortedParams = [...paramsList].sort((a, b) => b.param_name.length - a.param_name.length)

  // 2. 将表达式中的参数名替换为对应的参数值
  sortedParams.forEach(p => {
    // 使用 \b 匹配单词边界，确保精确匹配变量名
    const regex = new RegExp(`\\b${p.param_name}\\b`, 'g')
    evalStr = evalStr.replace(regex, p.param_value)
  })

  // 3. 计算表达式结果
  try {
    // 使用 new Function 代替直接的 eval，更加安全且适合计算数学表达式
    return new Function('return ' + evalStr)()
  } catch (e) {
    console.warn(`位宽表达式计算失败: ${expr} -> ${evalStr}`, e)
    return expr // 如果计算失败（比如表达式含有未解析的函数），返回原字符串兜底
  }
}

// 刷新所有端口的位宽
const updatePortWidths = (ports, newParams) => {
  if (!ports || !ports.length) return
  ports.forEach(port => {
    if (port.left_is_param && port.left_raw) {
      port.left = evaluateExpression(port.left_raw, newParams)
    }
    if (port.right_is_param && port.right_raw) {
      port.right = evaluateExpression(port.right_raw, newParams)
    }
  })
}

const saveParams = () => {
  // 1. 获取最新修改的参数
  const newParams = JSON.parse(JSON.stringify(editParams.value))
  
  // 2. 覆盖原有参数
  props.data.params = newParams

  // 3. 响应式更新输入输出端口的位宽
  updatePortWidths(props.data.in_ports, newParams)
  updatePortWidths(props.data.out_ports, newParams)
  nodeParamsChanged?.(props.id)

  // 4. 关闭弹窗
  isEditing.value = false
}

const menuState = ref({
  visible: false,
  x: 0,
  y: 0,
  port: null,
  type: '' // 记录是 'in' 还是 'out' 端口
})

// 处理端口的右键点击
const onPortRightClick = (event, port, type) => {
  menuState.value = {
    visible: true,
    x: event.clientX,
    y: event.clientY,
    port: port,
    type: type
  }
}

// 关闭右键菜单
const closeContextMenu = () => {
  menuState.value.visible = false
}

// 监听全局点击事件，点击其他地方时自动关闭菜单
onMounted(() => {
  window.addEventListener('click', closeContextMenu)
})

onUnmounted(() => {
  window.removeEventListener('click', closeContextMenu)
})


// ======== 注入父组件提供的方法 ========
const makeTopIO = inject('makeTopIO')
const disconnectPort = inject('disconnectPort') // <-- 1. 新增注入断开方法

const nodeParamsChanged = inject('nodeParamsChanged')

const handleMakeTopIO = () => {
  if (menuState.value.port) {
    if (menuState.value.type === 'in' && menuState.value.port._from && menuState.value.port._from.length > 0) {
      alert('该输入端口已经有连线，无法再引出为 Top IO！')
      closeContextMenu()
      return
    }
    makeTopIO(props.id, menuState.value.port, menuState.value.type)
  }
  closeContextMenu() 
}

// 2. 替换掉原来的假函数
const handleDisconnect = () => {
  if (menuState.value.port) {
    // 呼叫 App.vue 去执行断线和网表清理
    disconnectPort(props.id, menuState.value.port, menuState.value.type)
  }
  closeContextMenu() // 关掉菜单
}
</script>

<style scoped>
.verilog-module {
  background-color: #ffffff;
  border: 2px solid #2c3e50;
  border-radius: 6px;
  min-width: 160px;
  box-shadow: 0 4px 6px rgba(0,0,0,0.1);
  font-family: 'Fira Code', 'Consolas', monospace;
  transition: all 0.2s ease-in-out;
}

.verilog-module.is-selected {
  border-color: #268bd2; 
  box-shadow: 0 0 0 2px rgba(38, 139, 210, 0.3), 0 6px 12px rgba(0, 0, 0, 0.15); 
}

.module-header {
  background-color: #2c3e50;
  color: white;
  padding: 6px;
  text-align: center;
  font-weight: bold;
}

/* 参数区样式优化，增加交互反馈 */
.module-params {
  font-size: 10px;
  background: #fdf6e3;
  color: #b58900;
  padding: 4px;
  text-align: center;
  border-bottom: 1px solid #eee;
  cursor: pointer;
  transition: background-color 0.2s;
}
.module-params:hover {
  background: #eee8d5; /* 鼠标悬停加深颜色 */
}

.ports-container { display: flex; justify-content: space-between; padding: 10px 0; }
.port-row { 
  position: relative; 
  padding: 4px 10px; /* 上下稍微增加一点内边距，让背景色更好看 */
  display: flex; 
  align-items: center; 
  gap: 4px; 
  border-radius: 4px;
  transition: background-color 0.2s, transform 0.1s;
  cursor: context-menu; /* 提示用户可以右键 */
}

/* 鼠标悬浮时的微弱反馈 */
.port-row:hover {
  background-color: #f8f9fa;
}

/* ======== 新增：端口被右键选中（菜单打开）时的高亮状态 ======== */
.port-active {
  background-color: #e6f2ff !important; /* 浅蓝色背景 */
}

/* 左侧端口高亮时加个左边框装饰 */
.ports-left .port-active {
  box-shadow: inset 3px 0 0 #268bd2; 
}

/* 右侧端口高亮时加个右边框装饰 */
.ports-right .port-active {
  box-shadow: inset -3px 0 0 #268bd2; 
}

.right-align { justify-content: flex-end; }
.port-name { font-size: 12px; font-weight: 600; }
.port-width { font-size: 10px; color: #93a1a1; }
.custom-handle { width: 8px; height: 8px; border-radius: 2px; border: none; }
.target-handle { background: #dc322f; left: -4px; }
.source-handle { background: #859900; right: -4px; }

/* ======== 弹窗样式 ======== */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
  backdrop-filter: blur(2px);
}

.modal-content {
  background: white;
  border-radius: 6px;
  width: 320px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  font-family: 'Fira Code', 'Consolas', monospace;
}

.modal-header {
  background: #2c3e50;
  color: white;
  padding: 10px 16px;
  margin: 0;
}

.modal-header h3 {
  margin: 0;
  font-size: 14px;
}

.modal-body {
  padding: 16px;
  max-height: 400px;
  overflow-y: auto;
}

.form-group {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}

.form-group label {
  flex: 0 0 110px;
  font-weight: bold;
  color: #333;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.form-group input {
  flex: 1;
  padding: 4px 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-family: inherit;
  font-size: 12px;
}

.form-group input:focus {
  border-color: #268bd2;
  outline: none;
  box-shadow: 0 0 0 2px rgba(38, 139, 210, 0.2);
}

.modal-footer {
  padding: 10px 16px;
  border-top: 1px solid #eee;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  background: #fafafa;
}

.btn-cancel {
  background: white;
  border: 1px solid #ccc;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}
.btn-cancel:hover { background: #f0f0f0; }

.btn-primary {
  background: #268bd2;
  color: white;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}
.btn-primary:hover { background: #2176b3; }


.port-context-menu {
  position: fixed;
  background: white;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  min-width: 160px;
  z-index: 10000; /* 必须足够高，覆盖 Vue Flow 画布 */
  font-family: 'Fira Code', 'Consolas', monospace;
  overflow: hidden;
  /* 确保菜单不会阻挡其他事件，但自身可点击 */
  pointer-events: auto;
}

.menu-header {
  padding: 8px 12px;
  font-size: 11px;
  color: #93a1a1;
  background-color: #f8f9fa;
  border-bottom: 1px solid #ebeef5;
  font-weight: bold;
}

.menu-port-dir {
  font-weight: normal;
  font-size: 10px;
}

.menu-item {
  padding: 8px 12px;
  font-size: 12px;
  cursor: pointer;
  color: #333;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: background-color 0.2s;
}

.menu-item:hover {
  background-color: #f0f4ff;
  color: #268bd2;
}

.menu-item.text-danger:hover {
  background-color: #fff0f0;
  color: #dc322f;
}

</style>
