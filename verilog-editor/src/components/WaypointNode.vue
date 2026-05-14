<template>
  <div class=waypoint-node>
    <Handle type=target :position=Position.Left id=in />
    <Handle type=source :position=Position.Right id=out />
  </div>
</template>

<script setup>
import { Handle, Position } from '@vue-flow/core'
</script>

<style scoped>
.waypoint-node { width: 10px; height: 10px; background: #268bd2; border-radius: 50%; }
</style>
