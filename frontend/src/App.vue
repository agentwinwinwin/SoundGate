<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Refresh, Monitor, Clock, Headset, Setting } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useDeviceStore } from '@/stores/device'
import { useAuthStore } from '@/stores/auth'

const route = useRoute(); const router = useRouter(); const store = useDeviceStore()
const auth = useAuthStore()
const id = computed(() => String(route.params.id || store.selectedId))
watch(() => route.params.id, (value) => { if (value && store.devices.some(device => device.id === value)) store.select(String(value)) }, { immediate: true })
async function loadDeviceContext() {
  await store.loadDevices()
  const routeId = route.params.id ? String(route.params.id) : ''
  if (routeId && !store.devices.some(device => device.id === routeId) && store.selectedId) {
    const suffix = route.path.match(/^\/devices\/[^/]+\/(schedule|audio|settings)$/)?.[1]
    await router.replace(suffix ? `/devices/${store.selectedId}/${suffix}` : `/devices/${store.selectedId}`)
  }
  await store.loadSchedule()
}
onMounted(async () => { if (auth.authenticated) await loadDeviceContext() })
watch(() => auth.token, async token => { if (token) await loadDeviceContext() })
const nav = computed(() => {
  const items = [{ label: '设备管理', path: '/devices', icon: Monitor }]
  if (!store.devices.length) return items
  return [...items, { label: '设备详情', path: `/devices/${id.value}`, icon: Monitor }, { label: '每周音量计划', path: `/devices/${id.value}/schedule`, icon: Clock }, { label: '街道语音 / 提示音', path: `/devices/${id.value}/audio`, icon: Headset }, { label: '设备设置', path: `/devices/${id.value}/settings`, icon: Setting }]
})
async function refresh() {
  const result = await store.syncOneNETDevices()
  await store.loadSchedule()
  if (result.errors.length) ElMessage.warning(`已同步 ${result.synced.length} 台，${result.errors.length} 台失败`)
  else ElMessage.success(`已从 OneNET 同步 ${result.synced.length} 台设备`)
}
function changeDevice(value: string) {
  store.select(value)
  if (route.path === '/devices') return
  const suffix = route.path.match(/^\/devices\/[^/]+\/(schedule|audio|settings)$/)?.[1]
  router.push(suffix ? `/devices/${value}/${suffix}` : `/devices/${value}`)
}
async function logout() { await auth.logout(); store.$reset(); await router.replace('/login') }
</script>

<template>
  <router-view v-if="route.meta.public" />
  <div v-else class="app-shell">
    <aside class="sidebar">
      <div class="logo">SoundGate<span>声控设备配置软件</span></div>
      <div v-if="store.devices.length" class="device-context">
        <label>当前配置设备</label>
        <el-select :model-value="store.selectedId" @change="changeDevice" placeholder="选择设备">
          <el-option v-for="device in store.devices" :key="device.id" :value="device.id" :label="device.name">
            <div class="device-option"><span>{{ device.name }}</span><small>{{ device.id }}</small></div>
          </el-option>
        </el-select>
        <small>{{ store.selected.id }} · {{ store.selected.online ? '在线' : '离线' }}</small>
      </div>
      <button v-for="item in nav" :key="item.label" class="nav" :class="{ active: route.path === item.path }" @click="router.push(item.path)">
        <el-icon><component :is="item.icon" /></el-icon><span>{{ item.label }}</span>
      </button>
    </aside>
    <main>
      <header class="topbar"><div class="crumb">SoundGate <span>/</span> <b>{{ route.name }}</b></div><div class="user-menu"><span class="user-name">{{ auth.username }}</span><el-button :icon="Refresh" @click="refresh">刷新状态</el-button><el-button @click="logout">退出</el-button></div></header>
      <div class="page-wrap"><router-view /></div>
    </main>
  </div>
</template>
