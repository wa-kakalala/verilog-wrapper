<template>
  <div class="top-io-node" :class="{ 'is-input': data.direction === 'in', 'is-output': data.direction === 'out' }">
    <span class="io-label">{{ data.port_name }}</span>
    <span class="io-width" v-if="data.left !== data.right">[{{ data.left }}:{{ data.right }}]</span>
    <Handle
      v-if="data.direction === 'in'"
      type="source"
      id="out"
      :position="Position.Right"
      class="custom-handle io-handle"
    />
    <Handle
      v-if="data.direction === 'out'"
      type="target"
      id="in"
      :position="Position.Left"
      class="custom-handle io-handle"
    />
  </div>
</template>

<script setup>
import { Handle, Position } from '@vue-flow/core'
defineProps({ id: String, data: { type: Object, required: true } })
</script>

<style scoped>
.top-io-node {
  display: flex; align-items: center; gap: 4px;
  padding: 6px 14px; border-radius: 20px;
  font-weight: bold; font-size: 12px;
  font-family: 'Fira Code', 'Consolas', monospace;
  position: relative;
}
.is-input { background: #e6f2ff; border: 2px solid #268bd2; color: #175a8a; }
.is-output { background: #fef0f0; border: 2px solid #dc322f; color: #8b1a1a; }
.io-label { white-space: nowrap; }
.io-width { font-size: 10px; opacity: 0.7; }
.custom-handle.io-handle { width: 8px; height: 8px; border-radius: 2px; border: none; }
.is-input .io-handle { background: #268bd2; }
.is-output .io-handle { background: #dc322f; }
</style>
