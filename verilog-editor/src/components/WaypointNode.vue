<template>
  <div class="waypoint-node">
    <Handle type="target" position="left" id="in" class="hidden-handle" :connectable="false" />
    <Handle type="source" position="right" id="out" class="hidden-handle" :connectable="false" />
  </div>
</template>

<script setup>
import { Handle } from '@vue-flow/core'
</script>

<style scoped>
/* 原有样式保持不变... */
.waypoint-node {
  width: 12px;
  height: 12px;
  background-color: #268bd2;
  border-radius: 50%;
  cursor: grab;
  box-shadow: 0 0 4px rgba(0,0,0,0.3);
  transition: transform 0.1s;
}
.waypoint-node:hover { transform: scale(1.2); }
.waypoint-node:active { cursor: grabbing; }

.hidden-handle {
  opacity: 0;
  width: 1px;
  height: 1px;
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  border: none;
}
</style>