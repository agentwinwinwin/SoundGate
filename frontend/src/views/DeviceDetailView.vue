<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useDeviceStore } from '@/stores/device'
import PageHeading from '@/components/PageHeading.vue'
import { deviceService } from '@/services/deviceService'
import type { Weekday } from '@/types/schedule'

const store = useDeviceStore(); const route = useRoute()
const volume = ref(0); const volumeSaving = ref(false); const volumeStatus = ref('')
const dayKeys: Weekday[] = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat']
const todayKey = dayKeys[new Date().getDay()]!
const todayLabel = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][new Date().getDay()]
const todaySchedule = computed(() => store.schedule[todayKey])
async function loadVolume() {
  try {
    const data = await deviceService.fetchOneNETParameters(store.selected.id, ['DftVolume'])
    const state = data.DftVolume
    const shown = state?.displayValue
    if (shown !== null && shown !== undefined && shown !== '') volume.value = Number(shown)
    if (state?.value !== null && state?.value !== undefined) store.selected.volume = Number(state.value)
  } catch (error: any) { ElMessage.error(error?.response?.data?.detail || '读取 OneNET 参数失败') }
}
onMounted(async () => { store.select(String(route.params.id)); await loadVolume() })
async function saveVolume() {
  volumeSaving.value = true; volumeStatus.value = '正在下发…'
  try {
    await deviceService.updateOneNETParameters(store.selected.id, { DftVolume: volume.value })
    volumeStatus.value = '命令已发送，等待终端上报'
    const deadline = Date.now() + 30000
    while (Date.now() < deadline) {
      await new Promise(resolve => window.setTimeout(resolve, 2000))
      try {
        const data = await deviceService.fetchOneNETParameters(store.selected.id, ['DftVolume'])
        const reported = data.DftVolume?.value
        if (reported !== null && reported !== undefined && Number(reported) === volume.value) {
          store.selected.volume = Number(reported); volumeStatus.value = '终端已确认'
          ElMessage.success('终端音量已更新'); return
        }
      } catch { /* 在总超时时间内继续查询 */ }
    }
    volumeStatus.value = '终端暂未确认'
    ElMessage.warning('命令已发送，但终端 30 秒内未上报实际音量')
  } catch (error: any) {
    volumeStatus.value = '保存失败'
    ElMessage.error(error?.response?.data?.detail || '音量设置失败')
  } finally { volumeSaving.value = false }
}
</script>
<template>
  <PageHeading title="设备详情" description="查看当前设备状态并进入各项配置。" />
  <section class="hero">
    <div><span class="eyebrow">当前设备</span><h2>{{ store.selected.name }}</h2><p>设备编号 {{ store.selected.id }} · {{ store.selected.online ? '当前在线' : '当前离线' }}</p></div>
    <div class="hero-stats"><div><b>{{ store.selected.enabled ? 'ON' : 'OFF' }}</b><span>运行状态</span></div><div><b>{{ store.selected.volume }} / 9</b><span>当前音量</span></div><div><b>{{ store.selected.gps }}</b><span>GPS 状态</span></div><div><b>{{ store.selected.cloudConnected ? '在线' : '离线' }}</b><span>云端连接</span></div></div>
  </section>
  <div class="detail-grid overview-grid">
    <section class="card volume-card"><div class="card-title"><div><h3>音量控制</h3><p>调整当前设备音量，设备开关请在设备管理页操作</p></div><span class="muted">{{ volumeStatus }}</span></div><el-form-item label="音量 0~9"><el-slider v-model="volume" :min="0" :max="9" show-input :disabled="volumeSaving" /></el-form-item><div class="right"><el-button type="primary" :loading="volumeSaving" @click="saveVolume">保存音量</el-button></div></section>
    <section class="card info-list device-summary"><div class="card-title"><h3>设备信息</h3></div><div><span>设备名称</span><b>{{ store.selected.name }}</b></div><div><span>设备编号</span><b>{{ store.selected.id }}</b></div><div><span>蓝牙名称</span><b>{{ store.selected.bluetoothName }}</b></div><div><span>最后通信</span><b>{{ store.selected.lastSeen || '暂无上报' }}</b></div></section>
  </div>
  <section class="card schedule-card"><div class="card-title"><div><h3>今日音量计划</h3><p>{{ todayLabel }} · 计划到点后自动下发当前时段音量</p></div></div><el-table :data="todaySchedule"><el-table-column prop="time" label="时间"/><el-table-column prop="volume" label="音量"/></el-table></section>
</template>

<style scoped>
.overview-grid{grid-template-columns:minmax(0,1.4fr) minmax(320px,.8fr);align-items:stretch}.overview-grid>.card{margin-bottom:0}.volume-card{display:flex;flex-direction:column;justify-content:space-between;min-height:230px}.device-summary{margin-top:0}.schedule-card{margin-top:18px}@media(max-width:1000px){.overview-grid{grid-template-columns:1fr}.overview-grid>.card{margin-bottom:0}}
</style>
