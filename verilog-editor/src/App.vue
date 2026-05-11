<template>
  <div class="editor-container">
    <div class="toolbar">
      <input type="file" @change="onFileChange" accept=".v" ref="fileInput" style="display: none" />
      <button @click="$refs.fileInput.click()">📂 上传并解析 .v 文件</button>
      <button @click="generateCode" class="btn-primary">🚀 生成 Top 模块</button>
      <button @click="printData">🔍 打印网表 (F12)</button>
    </div>

    <div class="main-content">
      
      <div class="left-sidebar">
        <div class="sidebar-header" title="模块库 (IP Catalog)">📦 IP</div>
        <div class="sidebar-body">
            <div class="module-item module-item-active" title="Add Convert slice" @click="addConvertNode">Convert</div>
            <div class="module-item module-item-active" title="Add Constant value" @click="addConstantNode">Constant</div>
            <div class="module-item module-item-active" title="Add Concat bus" @click="addConcatNode">Concat</div>
            <div class="module-item" draggable="true" title="SdfUnit2">SdfUnit2</div>
            <div class="module-item" draggable="true" title="TwiddleConvert8">TwiddleConvert8</div>
            <div class="module-item" draggable="true" title="ALU_32bit">ALU_32bit</div>
            <div class="module-item" draggable="true" title="AXI_Interface">AXI_Interface</div>
        </div>
      </div>

      <div class="canvas-wrapper">
        <VueFlow 
          v-model:nodes="nodes" 
          v-model:edges="edges" 
          :node-types="nodeTypes"
          @connect="onConnect"
          :edges-updatable="true"  
          @edge-update="onEdgeUpdate" 
          @edges-change="onEdgesChange"
          @edge-double-click="onEdgeDoubleClick" 
          @node-double-click="onNodeDoubleClick" 
          delete-key-code="Delete"
          :default-edge-options="{
              type: 'step', 
              animated: false, 
              style: { stroke: '#555555', strokeWidth: 2 }
          }"
        >
          <Background pattern-color="#ddd" :gap="16" />
          <Controls />
        </VueFlow>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, provide, onMounted, onUnmounted } from 'vue' 
import { VueFlow, addEdge, updateEdge, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import VerilogNode from './components/VerilogNode.vue'
import TopIONode from './components/TopIONode.vue'
import WaypointNode from './components/WaypointNode.vue' 

// 获取 Vue Flow 实例方法
const { project, getSelectedNodes } = useVueFlow()

const nodeTypes = { 
  verilogModule: VerilogNode,
  waypoint: WaypointNode,
  topIO: TopIONode
}

const nodes = ref([])
const edges = ref([])

const toNumber = (value, fallback = 0) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

const getPortWidth = (port) => Math.abs(toNumber(port.left) - toNumber(port.right)) + 1

const setParamValue = (params, name, value) => {
  const param = params.find(p => p.param_name === name)
  if (param) param.param_value = value
}

const evaluatePortExpression = (expr, params) => {
  if (expr === undefined || expr === null || expr === '') return 0
  let evalStr = String(expr)
  const sortedParams = [...params].sort((a, b) => b.param_name.length - a.param_name.length)
  sortedParams.forEach(p => {
    evalStr = evalStr.replace(new RegExp(`\\b${p.param_name}\\b`, 'g'), p.param_value)
  })

  try {
    const value = new Function('return ' + evalStr)()
    return Number.isFinite(Number(value)) ? Number(value) : value
  } catch (err) {
    return expr
  }
}

const refreshNodePortWidths = (nodeData) => {
  const refreshPort = (port) => {
    if (port.left_is_param && port.left_raw) {
      port.left = evaluatePortExpression(port.left_raw, nodeData.params || [])
    }
    if (port.right_is_param && port.right_raw) {
      port.right = evaluatePortExpression(port.right_raw, nodeData.params || [])
    }
  }

  nodeData.in_ports?.forEach(refreshPort)
  nodeData.out_ports?.forEach(refreshPort)
}

const syncConvertInputWidth = (convertNode, sourcePort) => {
  if (convertNode?.data?.kind !== 'convert' || !sourcePort) return
  const inputPort = convertNode.data.in_ports.find(p => p.port_name === 'din')
  if (!inputPort) return

  const sourceWidth = getPortWidth(sourcePort)
  const sourceRight = toNumber(sourcePort.right)
  const sourceLeft = sourceRight + sourceWidth - 1

  setParamValue(convertNode.data.params, 'IN_MSB', sourceLeft)
  setParamValue(convertNode.data.params, 'IN_LSB', sourceRight)
  inputPort.left = sourceLeft
  inputPort.right = sourceRight

  const selMsb = toNumber(convertNode.data.params.find(p => p.param_name === 'SEL_MSB')?.param_value)
  const selLsb = toNumber(convertNode.data.params.find(p => p.param_name === 'SEL_LSB')?.param_value)
  if (selMsb >= sourceWidth || selLsb >= sourceWidth || selMsb < selLsb) {
    setParamValue(convertNode.data.params, 'SEL_MSB', sourceLeft)
    setParamValue(convertNode.data.params, 'SEL_LSB', sourceRight)
  }
  refreshNodePortWidths(convertNode.data)
}

const createConcatInputPort = (index, oldPort = null) => ({
  port_name: `in${index}`,
  left_raw: '0',
  right_raw: '0',
  left: oldPort?.left ?? 0,
  right: oldPort?.right ?? 0,
  left_is_param: 0,
  right_is_param: 0,
  _from: oldPort?._from || []
})

const updateConcatOutputWidth = (concatNode) => {
  if (concatNode?.data?.kind !== 'concat') return
  const outputPort = concatNode.data.out_ports.find(port => port.port_name === 'dout')
  if (!outputPort) return

  const totalWidth = concatNode.data.in_ports.reduce((sum, port) => sum + getPortWidth(port), 0)
  outputPort.left = Math.max(totalWidth - 1, 0)
  outputPort.right = 0
}

const ensureConcatPorts = (concatNode) => {
  if (concatNode?.data?.kind !== 'concat') return
  const inputCount = Math.max(1, Math.floor(toNumber(
    concatNode.data.params.find(param => param.param_name === 'INPUTS')?.param_value,
    concatNode.data.in_ports.length || 2
  )))

  const oldPorts = concatNode.data.in_ports || []
  const keptPortNames = new Set(Array.from({ length: inputCount }, (_, index) => `in${index}`))
  edges.value
    .filter(edge => edge.data?.realTarget === concatNode.id && !keptPortNames.has(edge.data.realTargetHandle))
    .forEach(edge => cleanUpLogicLine(edge.data))

  concatNode.data.in_ports = Array.from({ length: inputCount }, (_, index) =>
    createConcatInputPort(index, oldPorts[index])
  )
  updateConcatOutputWidth(concatNode)
}

const syncConcatInputWidth = (concatNode, targetHandle, sourcePort) => {
  if (concatNode?.data?.kind !== 'concat' || !sourcePort) return
  const inputPort = concatNode.data.in_ports.find(port => port.port_name === targetHandle)
  if (!inputPort) return

  const sourceWidth = getPortWidth(sourcePort)
  inputPort.left = sourceWidth - 1
  inputPort.right = 0
  updateConcatOutputWidth(concatNode)
}

const hasVisualEdgeForInput = (nodeId, port, connection) => {
  return edges.value.some(edge =>
    edge.data?.realSource === connection.inst_id &&
    edge.data?.realSourceHandle === connection.port &&
    edge.data?.realTarget === nodeId &&
    edge.data?.realTargetHandle === port.port_name
  )
}

const hasVisualEdgeForOutput = (nodeId, port, connection) => {
  return edges.value.some(edge =>
    edge.data?.realSource === nodeId &&
    edge.data?.realSourceHandle === port.port_name &&
    edge.data?.realTarget === connection.inst_id &&
    edge.data?.realTargetHandle === connection.port
  )
}

const reconcileLogicConnections = () => {
  nodes.value.forEach(node => {
    if (node.type !== 'verilogModule') return

    node.data.in_ports?.forEach(port => {
      port._from = (port._from || []).filter(connection =>
        hasVisualEdgeForInput(node.id, port, connection)
      )
    })

    node.data.out_ports?.forEach(port => {
      port._to = (port._to || []).filter(connection =>
        hasVisualEdgeForOutput(node.id, port, connection)
      )
    })
  })
}

const addConvertNode = () => {
  const timestamp = Date.now()
  const convertNode = {
    id: `convert_${timestamp}`,
    type: 'verilogModule',
    position: { x: 120 + Math.random() * 120, y: 80 + Math.random() * 160 },
    data: {
      kind: 'convert',
      mdl_name: 'Convert',
      params: [
        { param_name: 'IN_MSB', param_value: 12, param_is_num: 1 },
        { param_name: 'IN_LSB', param_value: 0, param_is_num: 1 },
        { param_name: 'SEL_MSB', param_value: 7, param_is_num: 1 },
        { param_name: 'SEL_LSB', param_value: 0, param_is_num: 1 }
      ],
      in_ports: [
        {
          port_name: 'din',
          left_raw: 'IN_MSB',
          right_raw: 'IN_LSB',
          left: 12,
          right: 0,
          left_is_param: 1,
          right_is_param: 1,
          _from: []
        }
      ],
      out_ports: [
        {
          port_name: 'dout',
          left_raw: 'SEL_MSB-SEL_LSB',
          right_raw: '0',
          left: 7,
          right: 0,
          left_is_param: 1,
          right_is_param: 1,
          _to: []
        }
      ]
    }
  }

  nodes.value.push(convertNode)
}

const addConstantNode = () => {
  const timestamp = Date.now()
  const constantNode = {
    id: `constant_${timestamp}`,
    type: 'verilogModule',
    position: { x: 120 + Math.random() * 120, y: 80 + Math.random() * 160 },
    data: {
      kind: 'constant',
      mdl_name: 'Constant',
      params: [
        { param_name: 'WIDTH', param_value: 1, param_is_num: 1 },
        { param_name: 'VALUE', param_value: 0, param_is_num: 1 }
      ],
      in_ports: [],
      out_ports: [
        {
          port_name: 'dout',
          left_raw: 'WIDTH-1',
          right_raw: '0',
          left: 0,
          right: 0,
          left_is_param: 1,
          right_is_param: 1,
          _to: []
        }
      ]
    }
  }

  nodes.value.push(constantNode)
}

const addConcatNode = () => {
  const timestamp = Date.now()
  const concatNode = {
    id: `concat_${timestamp}`,
    type: 'verilogModule',
    position: { x: 120 + Math.random() * 120, y: 80 + Math.random() * 160 },
    data: {
      kind: 'concat',
      mdl_name: 'Concat',
      params: [
        { param_name: 'INPUTS', param_value: 2, param_is_num: 1 }
      ],
      in_ports: [
        createConcatInputPort(0),
        createConcatInputPort(1)
      ],
      out_ports: [
        {
          port_name: 'dout',
          left_raw: '',
          right_raw: '',
          left: 1,
          right: 0,
          left_is_param: 0,
          right_is_param: 0,
          _to: []
        }
      ]
    }
  }

  updateConcatOutputWidth(concatNode)
  nodes.value.push(concatNode)
}

// ==========================================
// 1. 处理拖拽连线端点改线 
// ==========================================
const onEdgeUpdate = ({ edge, connection }) => {
  // 利用老线的 data 清除原有的网表连接
  if (edge.data) {
    const { realSource, realTarget, realSourceHandle, realTargetHandle } = edge.data
    const oldSourceNode = nodes.value.find(n => n.id === realSource)
    const oldTargetNode = nodes.value.find(n => n.id === realTarget)

    if (oldSourceNode?.type === 'verilogModule' && oldSourceNode.data.out_ports) {
      const outPort = oldSourceNode.data.out_ports.find(p => p.port_name === realSourceHandle)
      if (outPort) outPort._to = outPort._to.filter(t => t.inst_id !== realTarget)
    }
    if (oldTargetNode?.type === 'verilogModule' && oldTargetNode.data.in_ports) {
      const inPort = oldTargetNode.data.in_ports.find(p => p.port_name === realTargetHandle)
      if (inPort) inPort._from = inPort._from.filter(f => f.inst_id !== realSource)
    }
  }

  // 验证新的目标并写入新网表
  const newSourceNode = nodes.value.find(n => n.id === connection.source)
  const newTargetNode = nodes.value.find(n => n.id === connection.target)

  if (newSourceNode?.type === 'verilogModule' && newTargetNode?.type === 'verilogModule') {
    const outPort = newSourceNode.data.out_ports.find(p => p.port_name === connection.sourceHandle)
    const inPort = newTargetNode.data.in_ports.find(p => p.port_name === connection.targetHandle)

    if (outPort && inPort) {
      syncConvertInputWidth(newTargetNode, outPort)
      syncConcatInputWidth(newTargetNode, connection.targetHandle, outPort)
      if (inPort._from && inPort._from.length > 0) {
        alert(`连线错误：输入端口 ${inPort.port_name} 已经被驱动！`)
        return
      }
      if (outPort.left !== inPort.left || outPort.right !== inPort.right) {
        alert(`位宽不匹配！无法连接 [${outPort.left}:${outPort.right}] 到 [${inPort.left}:${inPort.right}]`)
        return 
      }
      outPort._to.push({ inst_id: connection.target, port: connection.targetHandle })
      inPort._from.push({ inst_id: connection.source, port: connection.sourceHandle })
    }
  }

  // 更新视觉连线，并强制覆写它体内的真实身份 data
  const updatedEdges = updateEdge(edge, connection, edges.value)
  edges.value = updatedEdges.map(e => {
    if (e.id === edge.id || (e.source === connection.source && e.target === connection.target)) {
      return {
        ...e,
        data: {
          realSource: connection.source,
          realSourceHandle: connection.sourceHandle,
          realTarget: connection.target,
          realTargetHandle: connection.targetHandle
        }
      }
    }
    return e
  })
}

// ==========================================
// 2. 双击连线生成拐点 
// ==========================================
const onEdgeDoubleClick = (params) => {
  const { event, edge } = params
  event.preventDefault()

  const position = project({ x: event.clientX, y: event.clientY })

  const waypointId = `wp_${Date.now()}`
  const waypointNode = {
    id: waypointId,
    type: 'waypoint',
    position: position,
  }

  const edge1 = {
    id: `e_${edge.source}_${waypointId}`,
    source: edge.source, sourceHandle: edge.sourceHandle,
    target: waypointId, targetHandle: 'in', 
    type: 'step', animated: edge.animated, style: edge.style,
    data: { ...edge.data } 
  }

  const edge2 = {
    id: `e_${waypointId}_${edge.target}`,
    source: waypointId, sourceHandle: 'out',
    target: edge.target, targetHandle: edge.targetHandle,
    type: 'step', animated: edge.animated, style: edge.style,
    data: { ...edge.data } 
  }

  edges.value = edges.value.filter(e => e.id !== edge.id)
  nodes.value.push(waypointNode)
  edges.value.push(edge1, edge2)
}

// ==========================================
// 3. 双击拐点，线段自愈 (Heal)
// ==========================================
const onNodeDoubleClick = ({ event, node }) => {
  if (node.type === 'waypoint') {
    event.preventDefault()
    
    const edgeIn = edges.value.find(e => e.target === node.id)
    const edgeOut = edges.value.find(e => e.source === node.id)

    if (edgeIn && edgeOut) {
      const healedEdge = {
        id: `e_${edgeIn.source}_${edgeOut.target}_${Date.now()}`,
        source: edgeIn.source, sourceHandle: edgeIn.sourceHandle,
        target: edgeOut.target, targetHandle: edgeOut.targetHandle,
        type: 'step', animated: edgeIn.animated, style: edgeIn.style,
        data: { ...edgeIn.data }
      }

      nodes.value = nodes.value.filter(n => n.id !== node.id)
      edges.value = edges.value.filter(e => e.id !== edgeIn.id && e.id !== edgeOut.id)
      edges.value.push(healedEdge)
    }
  }
}

// ==========================================
// 4. 统一网表清理引擎 (核心防御机制)
// ==========================================
const cleanUpLogicLine = (edgeData) => {
  if (!edgeData) return
  const { realSource, realTarget, realSourceHandle, realTargetHandle } = edgeData

  const sourceNode = nodes.value.find(n => n.id === realSource)
  const targetNode = nodes.value.find(n => n.id === realTarget)

  if (sourceNode?.type === 'verilogModule' && sourceNode.data.out_ports) {
    const outPort = sourceNode.data.out_ports.find(p => p.port_name === realSourceHandle)
    if (outPort) outPort._to = outPort._to.filter(t => t.inst_id !== realTarget)
  }
  if (targetNode?.type === 'verilogModule' && targetNode.data.in_ports) {
    const inPort = targetNode.data.in_ports.find(p => p.port_name === realTargetHandle)
    if (inPort) inPort._from = inPort._from.filter(f => f.inst_id !== realSource)
    if (targetNode.data.kind === 'concat' && inPort) {
      inPort.left = 0
      inPort.right = 0
      updateConcatOutputWidth(targetNode)
    }
  }

  let edgesToKeep = []
  let waypointsToRemove = new Set()

  edges.value.forEach(e => {
    if (e.data &&
        e.data.realSource === realSource &&
        e.data.realTarget === realTarget &&
        e.data.realSourceHandle === realSourceHandle &&
        e.data.realTargetHandle === realTargetHandle) {
      
      if (e.source.startsWith('wp_')) waypointsToRemove.add(e.source)
      if (e.target.startsWith('wp_')) waypointsToRemove.add(e.target)
    } else {
      edgesToKeep.push(e)
    }
  })

  edges.value = edgesToKeep
  if (waypointsToRemove.size > 0) {
    nodes.value = nodes.value.filter(n => !waypointsToRemove.has(n.id))
  }

  // Remove Top IO nodes when their connecting edge is deleted
  const topIOToRemove = new Set()
  if (sourceNode?.type === 'topIO' || sourceNode?.data?.is_top_io) topIOToRemove.add(realSource)
  if (targetNode?.type === 'topIO' || targetNode?.data?.is_top_io) topIOToRemove.add(realTarget)
  if (topIOToRemove.size > 0) {
    nodes.value = nodes.value.filter(n => !topIOToRemove.has(n.id))
  }
}

// ==========================================
// 5. 拦截键盘 Delete 操作
// ==========================================
const getEdgeIdentity = (edge) => {
  if (edge?.data) return edge.data
  if (!edge) return null

  return {
    realSource: edge.source,
    realSourceHandle: edge.sourceHandle,
    realTarget: edge.target,
    realTargetHandle: edge.targetHandle
  }
}

const onEdgesChange = (changes) => {
  changes
    .filter(change => change.type === 'remove')
    .forEach(change => {
      const removedEdge = edges.value.find(edge => edge.id === change.id)
      const relatedWaypointEdge = edges.value.find(edge =>
        edge.data &&
        (edge.source === change.source ||
          edge.target === change.source ||
          edge.source === change.target ||
          edge.target === change.target)
      )
      cleanUpLogicLine(getEdgeIdentity(removedEdge || relatedWaypointEdge || change))
    })
  reconcileLogicConnections()
}

// ==========================================
// 6. 处理右键菜单的 "断开端口连接"
// ==========================================
const handleDisconnectPort = (nodeId, port, type) => {
  const relatedEdge = edges.value.find(e => {
    if (!e.data) return false
    if (type === 'out') {
      return e.data.realSource === nodeId && e.data.realSourceHandle === port.port_name
    } else {
      return e.data.realTarget === nodeId && e.data.realTargetHandle === port.port_name
    }
  })

  if (relatedEdge) {
    cleanUpLogicLine(relatedEdge.data)
  }
}

provide('disconnectPort', handleDisconnectPort)

const handleNodeParamsChanged = (nodeId) => {
  const node = nodes.value.find(item => item.id === nodeId)
  if (!node) return

  ensureConcatPorts(node)
}

provide('nodeParamsChanged', handleNodeParamsChanged)

// ==========================================
// 7. 模块复制与粘贴 (Ctrl+C / Ctrl+V)
// ==========================================
const copiedNodes = ref([])

const handleKeyDown = (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
  const isCtrlOrCmd = e.ctrlKey || e.metaKey 

  // Ctrl + C 复制
  if (isCtrlOrCmd && e.key.toLowerCase() === 'c') {
    const selected = getSelectedNodes.value.filter(n => n.type === 'verilogModule')
    if (selected.length > 0) {
      copiedNodes.value = JSON.parse(JSON.stringify(selected))
    }
  }

  // Ctrl + V 粘贴
  if (isCtrlOrCmd && e.key.toLowerCase() === 'v') {
    if (copiedNodes.value.length > 0) {
      const newNodes = copiedNodes.value.map(node => {
        const newId = `${node.data.mdl_name}_copy_${Date.now()}_${Math.floor(Math.random() * 1000)}`
        
        // 深拷贝并彻底清空连线状态
        const newData = JSON.parse(JSON.stringify(node.data))
        if (newData.in_ports) newData.in_ports.forEach(p => p._from = [])
        if (newData.out_ports) newData.out_ports.forEach(p => p._to = [])

        return {
          id: newId,
          type: 'verilogModule',
          position: { x: node.position.x + 30, y: node.position.y + 30 },
          data: newData
        }
      })

      nodes.value.push(...newNodes)
    }
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
})
onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})

// ==========================================
// 8. 其他基础设施 (上传、连线、TopIO)
// ==========================================
const onFileChange = async (event) => {
  const file = event.target.files[0]
  if (!file) return

  const formData = new FormData()
  formData.append('file', file)

  try {
    const res = await fetch('http://localhost:8000/library', { method: 'POST', body: formData })
    const moduleData = await res.json()
    
    moduleData.out_ports.forEach(p => p._to = p._to || [])
    moduleData.in_ports.forEach(p => p._from = p._from || [])
    
    const newNode = {
      id: `${moduleData.mdl_name}_${Date.now()}`,
      type: 'verilogModule',
      position: { x: Math.random() * 200 + 50, y: Math.random() * 200 + 50 },
      data: moduleData
    }
    nodes.value.push(newNode)
  } catch (err) {
    alert('解析失败，请检查后端服务是否开启')
  } finally {
    event.target.value = ''
  }
}

// 首次连线注入真实端点数据
const onConnect = (params) => {
  reconcileLogicConnections()

  const sourceNode = nodes.value.find(n => n.id === params.source)
  const targetNode = nodes.value.find(n => n.id === params.target)
  
  if (sourceNode?.type !== 'verilogModule' || targetNode?.type !== 'verilogModule') {
    edges.value = addEdge({ ...params, type: 'step' }, edges.value)
    return
  }

  const outPort = sourceNode.data.out_ports.find(p => p.port_name === params.sourceHandle)
  const inPort = targetNode.data.in_ports.find(p => p.port_name === params.targetHandle)

  if (!outPort || !inPort) return
  syncConvertInputWidth(targetNode, outPort)
  syncConcatInputWidth(targetNode, params.targetHandle, outPort)
  if (inPort._from && inPort._from.length > 0) {
    alert(`连线错误：输入端口 ${inPort.port_name} 已经被驱动！`)
    return
  }
  if (outPort.left !== inPort.left || outPort.right !== inPort.right) {
    alert(`位宽不匹配！无法连接 [${outPort.left}:${outPort.right}] 到 [${inPort.left}:${inPort.right}]`)
    return
  }

  const isBus = outPort.left !== outPort.right || outPort.left !== "0"
  
  const customEdgeParams = {
    ...params,
    type: 'step', 
    animated: isBus, 
    style: {
      stroke: isBus ? '#d33682' : '#268bd2', 
      strokeWidth: isBus ? 4 : 2,            
    },
    data: {
      realSource: params.source,
      realSourceHandle: params.sourceHandle,
      realTarget: params.target,
      realTargetHandle: params.targetHandle
    }
  }

  edges.value = addEdge(customEdgeParams, edges.value)

  outPort._to.push({ inst_id: params.target, port: params.targetHandle })
  inPort._from.push({ inst_id: params.source, port: params.sourceHandle })
}

// Top IO 引出
const handleMakeTopIO = (nodeId, port, type) => {
  const targetNode = nodes.value.find(n => n.id === nodeId)
  if (!targetNode) return

  const offsetX = type === 'in' ? -200 : 250
  const offsetY = Math.random() * 20 - 10 

  const ioNodeId = `TOP_IO_${port.port_name}_${Date.now()}`
  const isBus = port.left !== port.right || port.left !== "0"
  
  const ioNode = {
    id: ioNodeId,
    type: 'topIO', 
    position: { 
      x: targetNode.position.x + offsetX, 
      y: targetNode.position.y + offsetY 
    },
    data: {
      is_top_io: true, 
      port_name: port.port_name,
      left: port.left, right: port.right, direction: type
    },
  }
  
  nodes.value.push(ioNode)

  const newEdge = {
    id: `e_${ioNodeId}_${nodeId}_${port.port_name}`,
    source: type === 'in' ? ioNodeId : nodeId,
    target: type === 'in' ? nodeId : ioNodeId,
    sourceHandle: type === 'in' ? 'out' : port.port_name,
    targetHandle: type === 'in' ? port.port_name : 'in',
    type: 'step', animated: isBus,
    style: { stroke: type === 'in' ? '#268bd2' : '#dc322f', strokeWidth: isBus ? 3 : 2 },
    data: {
      realSource: type === 'in' ? ioNodeId : nodeId,
      realSourceHandle: type === 'in' ? 'out' : port.port_name,
      realTarget: type === 'in' ? nodeId : ioNodeId,
      realTargetHandle: type === 'in' ? port.port_name : 'in',
    }
  }
  
  edges.value.push(newEdge)

  if (type === 'in') {
    port._from.push({ inst_id: ioNodeId, port: port.port_name })
  } else {
    port._to.push({ inst_id: ioNodeId, port: port.port_name })
  }
}

provide('makeTopIO', handleMakeTopIO)

const generateCode = () => { /* 调用后端 API */ }
const printData = () => { console.log(nodes.value, edges.value) }

</script>

<style>
@import '@vue-flow/core/dist/style.css';
@import '@vue-flow/core/dist/theme-default.css';
@import '@vue-flow/controls/dist/style.css';

html, body, #app { margin: 0; padding: 0; height: 100%; width: 100%; overflow: hidden; }

.editor-container { display: flex; flex-direction: column; height: 100vh; }
.toolbar { padding: 10px; background: #eee; display: flex; gap: 10px; border-bottom: 1px solid #ccc; z-index: 10; }

button { padding: 6px 12px; cursor: pointer; border: 1px solid #ccc; border-radius: 4px; background: white; }
button:hover { background: #f0f0f0; }
.btn-primary { background: #268bd2; color: white; border: none; }
.btn-primary:hover { background: #2176b3; }

/* ======== 左右分栏核心布局 ======== */
.main-content {
  display: flex;
  flex: 1; 
  overflow: hidden;
}

/* 左侧边栏样式：极致紧凑版 (60px) */
.left-sidebar {
  width: 60px; /* <--- 再次缩窄到 60px */
  background-color: #f8f9fa;
  border-right: 1px solid #dcdfe6;
  display: flex;
  flex-direction: column;
  box-shadow: 2px 0 5px rgba(0,0,0,0.02);
  z-index: 5;
}

.sidebar-header {
  padding: 10px 2px; /* 极限压缩内边距 */
  background-color: #e9ecef;
  border-bottom: 1px solid #dcdfe6;
  font-weight: bold;
  font-size: 12px;
  color: #2c3e50;
  text-align: center;
  cursor: default;
}

.sidebar-body {
  padding: 8px 4px; /* 极限压缩内边距 */
  flex: 1;
  overflow-y: auto; 
  display: flex;
  flex-direction: column;
  gap: 6px; 
}

/* 侧边栏的模块按钮：极限压缩 */
.module-item {
  padding: 6px 2px; /* 上下6px，左右几乎贴边 */
  background: white;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-family: 'Fira Code', 'Consolas', monospace; 
  font-size: 10px; /* 字体缩小到10px */
  text-align: center;
  cursor: grab; 
  transition: all 0.2s;
  
  /* 必须保留打点省略，否则会撑破 60px 的宽度 */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.module-item:hover {
  border-color: #268bd2;
  color: #268bd2;
  box-shadow: 0 2px 4px rgba(38, 139, 210, 0.1);
  transform: translateY(-1px);
}

.module-item-active {
  border-color: #268bd2;
  background: #e6f2ff;
  color: #175a8a;
  font-weight: 700;
}

.module-item:active {
  cursor: grabbing;
}
/* 右侧画布占满剩余空间 */
.canvas-wrapper { flex: 1; position: relative; }

/* ======== Edge Selection Highlight ======== */
.vue-flow__edge.selected .vue-flow__edge-path {
  stroke: #ff6b35 !important;
  stroke-width: 3px !important;
  filter: drop-shadow(0 0 5px rgba(255, 107, 53, 0.6));
}

.vue-flow__edge.selected .vue-flow__edge-text {
  font-weight: bold;
}
</style>
