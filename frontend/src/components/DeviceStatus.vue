<script setup lang="ts">defineProps<{ online: boolean }>()</script>
<template><span class="status" :class="online ? 'online' : 'offline'"><i />{{ online ? '在线' : '离线' }}</span></template>
