<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useDeviceStore } from '@/stores/device'
import { deviceService } from '@/services/deviceService'
import { fetchCommand, type OneNETParameters, type OneNETParameterState } from '@/api/devices'
import DeviceStatus from '@/components/DeviceStatus.vue'
import PageHeading from '@/components/PageHeading.vue'

const store = useDeviceStore(); const route = useRoute()
const bluetoothForm = reactive({ name: '', password: '' })
const workForm = reactive({ DftStHour: 0, DftStMinute: 0, DtfEdHour: 23, DftEdMinute: 59 })
const parameterState = ref<Partial<Record<keyof OneNETParameters, OneNETParameterState>>>({})
const loading = ref(false); const saving = ref(false)
const bluetoothSaving = ref(false)
const startTime = computed(() => `${String(workForm.DftStHour).padStart(2, '0')}:${String(workForm.DftStMinute).padStart(2, '0')}`)
const endTime = computed(() => `${String(workForm.DtfEdHour).padStart(2, '0')}:${String(workForm.DftEdMinute).padStart(2, '0')}`)
const stateText = (key: keyof OneNETParameters) => {
  const state = parameterState.value[key]
  return state ? `终端实际：${state.value ?? '未上报'}` : '暂无终端数据'
}
async function loadWorkParameters() {
  loading.value = true
  try {
    const keys = Object.keys(workForm) as (keyof OneNETParameters)[]
    const data = await deviceService.fetchOneNETParameters(store.selected.id, keys); parameterState.value = data
    for (const key of Object.keys(workForm) as (keyof typeof workForm)[]) {
      const value = data[key]?.displayValue
      if (value !== null && value !== undefined && value !== '') workForm[key] = Number(value)
    }
  } catch (error: any) { ElMessage.error(error?.response?.data?.detail || '读取 OneNET 工作参数失败') }
  finally { loading.value = false }
}
async function saveWorkParameters() {
  saving.value = true
  try {
    await deviceService.updateOneNETParameters(store.selected.id, { ...workForm }); await loadWorkParameters()
    ElMessage.success('工作参数已发送到终端，等待终端上报确认')
  } catch (error: any) { ElMessage.error(error?.response?.data?.detail || '工作参数保存失败') }
  finally { saving.value = false }
}
async function submitBluetooth() {
  if (!bluetoothForm.name.trim()) return ElMessage.warning('请输入新蓝牙名称')
  bluetoothSaving.value = true
  try {
    const result = await store.renameBluetooth(bluetoothForm.name.trim(), bluetoothForm.password); bluetoothForm.password = ''
    ElMessage.info('修改命令已发送，正在等待终端响应')
    for (let i = 0; i < 30; i++) {
      await new Promise(resolve => setTimeout(resolve, 1000))
      const command = await fetchCommand(store.selected.id, result.requestId)
      if (command.status === 'succeeded') { ElMessage.success('终端已确认修改，真实名称将在设备回报后更新'); return }
      if (command.status === 'failed') throw new Error(command.error || '终端响应失败')
    }
    ElMessage.warning('终端暂未响应，可稍后重新读取')
  }
  catch (error: any) { ElMessage.error(error?.response?.data?.detail || error?.message || '修改失败') }
  finally { bluetoothSaving.value = false }
}
onMounted(async () => { store.select(String(route.params.id)); bluetoothForm.name = store.selected.bluetoothName; await loadWorkParameters() })
</script>

<template>
  <PageHeading title="设备设置" description="配置终端工作时间，并查看信号机接口约定。"><el-button :loading="loading" @click="loadWorkParameters">重新读取</el-button></PageHeading>
  <section class="card">
    <div class="card-title"><div><h3>终端工作时段</h3><p>参数设置使能开启后，终端每天按此时段工作</p></div><el-tag>{{ startTime }} — {{ endTime }}</el-tag></div>
    <el-form label-position="top" :disabled="loading || saving"><div class="parameter-grid">
      <el-form-item label="开始小时 (DftStHour)"><el-input-number v-model="workForm.DftStHour" :min="0" :max="23"/><small>{{ stateText('DftStHour') }}</small></el-form-item>
      <el-form-item label="开始分钟 (DftStMinute)"><el-input-number v-model="workForm.DftStMinute" :min="0" :max="59"/><small>{{ stateText('DftStMinute') }}</small></el-form-item>
      <el-form-item label="结束小时 (DtfEdHour)"><el-input-number v-model="workForm.DtfEdHour" :min="0" :max="23"/><small>{{ stateText('DtfEdHour') }}</small></el-form-item>
      <el-form-item label="结束分钟 (DftEdMinute)"><el-input-number v-model="workForm.DftEdMinute" :min="0" :max="59"/><small>{{ stateText('DftEdMinute') }}</small></el-form-item>
    </div></el-form>
  </section>
  <section class="card">
    <div class="card-title"><div><h3>信号机接口</h3><p>终端按外部信号工作，不再由平台写 Period、RushTime、WalkTime</p></div><el-tag type="warning">协议待信号机厂商确认</el-tag></div>
    <div class="signal-contract"><span><b>开关输入</b> 1 路</span><span><b>绿灯输入</b> 1 路</span><span><b>红灯输入</b> 1 路</span><span><b>RS-485</b> 帧格式、波特率、地址和校验方式待提供</span></div>
    <div class="action-row"><span class="muted">DftEnable 在设备管理页设置；DftVolume 在设备详情和音量计划中设置。</span><el-button type="primary" :loading="saving" :disabled="loading" @click="saveWorkParameters">保存工作时段并下发</el-button></div>
  </section>
  <div class="detail-grid">
    <section class="card info-list"><div class="card-title"><h3>设备信息</h3></div><div><span>设备名称</span><b>{{ store.selected.name }}</b></div><div><span>设备编号</span><b>{{ store.selected.id }}</b></div><div><span>当前蓝牙名称</span><b>{{ store.selected.bluetoothName }}</b></div><div><span>在线状态</span><DeviceStatus :online="store.selected.online"/></div></section>
    <section class="card"><div class="card-title"><div><h3>修改蓝牙名称</h3><p>需要管理密码验证</p></div></div><el-form label-position="top" :disabled="bluetoothSaving"><el-form-item label="新蓝牙名称"><el-input v-model="bluetoothForm.name" maxlength="32" show-word-limit/></el-form-item><el-form-item label="管理密码"><el-input v-model="bluetoothForm.password" type="password" show-password autocomplete="current-password"/></el-form-item><el-button type="primary" :loading="bluetoothSaving" @click="submitBluetooth">验证并修改</el-button></el-form></section>
  </div>
</template>

<style scoped>
.parameter-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:18px}.parameter-grid small{display:block;margin-top:8px;color:#8290a6;font-size:12px}.parameter-grid :deep(.el-input-number){width:100%}.signal-contract{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.signal-contract span{padding:16px;border-radius:16px;background:#f5f7fb;color:#66758c}.signal-contract b{display:block;margin-bottom:5px;color:#182c49}.action-row{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-top:20px}@media(max-width:1000px){.parameter-grid,.signal-contract{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:640px){.parameter-grid,.signal-contract{grid-template-columns:1fr}.action-row{align-items:stretch;flex-direction:column}}
</style>
