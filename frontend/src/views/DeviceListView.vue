<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useDeviceStore } from '@/stores/device'
import { deviceService } from '@/services/deviceService'
import type { OneNETDevice } from '@/api/devices'
import type { Device } from '@/types/device'
import DeviceStatus from '@/components/DeviceStatus.vue'
import PageHeading from '@/components/PageHeading.vue'

const store = useDeviceStore()
const query = ref('')
const switching = reactive<Record<string, boolean>>({})
const switchStatus = reactive<Record<string, string>>({})
const addVisible = ref(false)
const adding = ref(false)
const cloudLoading = ref(false)
const cloudDevices = ref<OneNETDevice[]>([])
const selectedCloudDevices = ref<string[]>([])
const filtered = computed(() => {
  const value = query.value.trim().toLowerCase()
  return value
    ? store.devices.filter(device => device.name.toLowerCase().includes(value) || device.streetName.toLowerCase().includes(value) || device.id.toLowerCase().includes(value))
    : store.devices
})

async function remove(device: Device) {
  try {
    await ElMessageBox.confirm(`删除后将同时移除 ${device.name} 的周计划和音频配置，且无法恢复。`, '删除设备', { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' })
    await store.deleteDevice(device.id)
    ElMessage.success('设备已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error('删除失败，请检查后端连接')
  }
}

async function openAddDevice() {
  addVisible.value = true
  cloudLoading.value = true
  selectedCloudDevices.value = []
  try {
    cloudDevices.value = (await deviceService.fetchOneNETDevices()).devices
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '读取 OneNET 设备失败')
  } finally {
    cloudLoading.value = false
  }
}

async function addDevice() {
  if (!selectedCloudDevices.value.length) return ElMessage.warning('请选择需要加入的 OneNET 设备')
  adding.value = true
  try {
    const imported = await store.importOneNETDevices(selectedCloudDevices.value)
    addVisible.value = false
    ElMessage.success(`已添加 ${imported.length} 台真实设备`)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '添加失败，请检查 OneNET 连接')
  } finally {
    adding.value = false
  }
}

async function toggleDevice(device: Device, enabled: string | number | boolean) {
  const target = Boolean(enabled)
  const previous = !target
  switching[device.id] = true
  switchStatus[device.id] = `正在下发${target ? '开启' : '关闭'}命令…`
  try {
    await deviceService.updateOneNETParameters(device.id, { DftEnable: target ? 1 : 0 })
    switchStatus[device.id] = '命令已发送，等待终端响应…'
    ElMessage.info({ message: `${device.name} 命令已下发，正在等待终端上报`, duration: 3000 })

    let confirmed = false
    const deadline = Date.now() + 30000
    while (Date.now() < deadline) {
      await new Promise(resolve => window.setTimeout(resolve, 2000))
      try {
        const parameters = await deviceService.fetchOneNETParameters(device.id, ['DftEnable'])
        const reported = parameters.DftEnable?.value
        if (reported !== null && reported !== undefined && Number(reported) === (target ? 1 : 0)) {
          confirmed = true
          break
        }
      } catch { /* 短暂查询失败时继续等到总超时时间 */ }
    }

    if (!confirmed) {
      device.enabled = previous
      switchStatus[device.id] = '终端未响应'
      ElMessage.warning({ message: `${device.name} 30 秒内未上报实际状态，请检查终端连接`, duration: 6000 })
      return
    }
    device.enabled = target
    switchStatus[device.id] = '终端已确认'
    ElMessage.success(`${device.name} 已确认切换为 ${target ? 'ON' : 'OFF'}`)
  } catch (error: any) {
    device.enabled = previous
    switchStatus[device.id] = '下发失败'
    ElMessage.error(error?.response?.data?.detail || '状态切换失败，请检查后端连接')
  } finally {
    switching[device.id] = false
  }
}
</script>

<template>
  <PageHeading title="设备管理" description="管理当前账号下的声控终端。">
    <el-button type="primary" @click="openAddDevice">＋ 添加设备</el-button>
  </PageHeading>
  <section class="card">
    <div class="search"><el-input v-model="query" clearable :prefix-icon="Search" placeholder="搜索设备名称 / 街道名称" /></div>
    <el-table :data="filtered" row-key="id" empty-text="当前账号暂无设备">
      <el-table-column label="设备名称" min-width="210"><template #default="{ row }"><b>{{ row.name }}</b></template></el-table-column>
      <el-table-column label="街道名称" min-width="210"><template #default="{ row }">{{ row.streetName || '未设置' }}</template></el-table-column>
      <el-table-column label="在线状态" width="120"><template #default="{ row }"><DeviceStatus :online="row.online" /></template></el-table-column>
      <el-table-column label="当前状态" width="210"><template #default="{ row }"><div class="device-switch"><el-switch v-model="row.enabled" inline-prompt active-text="ON" inactive-text="OFF" :disabled="!row.online || switching[row.id]" :loading="switching[row.id]" @change="toggleDevice(row, $event)" /><small v-if="switchStatus[row.id]" :class="{ pending: switching[row.id] }">{{ switchStatus[row.id] }}</small></div></template></el-table-column>
      <el-table-column label="当前音量" width="120"><template #default="{ row }">{{ row.online ? `${row.volume} / 9` : '—' }}</template></el-table-column>
      <el-table-column width="130"><template #default="{ row }"><el-button type="danger" plain @click="remove(row)">删除设备</el-button></template></el-table-column>
    </el-table>
  </section>
  <el-dialog v-model="addVisible" title="从 OneNET 添加设备" width="480px" destroy-on-close>
    <div v-loading="cloudLoading" style="min-height: 120px">
      <el-empty v-if="!cloudLoading && !cloudDevices.length" description="OneNET 产品下暂无设备" />
      <el-checkbox-group v-else v-model="selectedCloudDevices">
        <div v-for="device in cloudDevices" :key="device.deviceName" style="padding: 10px 0">
          <el-checkbox :value="device.deviceName" :disabled="device.added || device.claimed">
            {{ device.deviceName }} · {{ device.online ? '在线' : '离线' }}
            <span v-if="device.added">（已添加）</span>
            <span v-else-if="device.claimed">（已属于其他账号）</span>
          </el-checkbox>
        </div>
      </el-checkbox-group>
    </div>
    <template #footer>
      <el-button @click="addVisible = false">取消</el-button>
      <el-button type="primary" :loading="adding" @click="addDevice">加入当前账号</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.device-switch { display: flex; align-items: center; gap: 10px; }
.device-switch small { color: #718096; white-space: nowrap; }
.device-switch small.pending { color: #e6a23c; }
</style>
