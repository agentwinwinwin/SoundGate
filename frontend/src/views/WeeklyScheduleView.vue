<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useDeviceStore } from '@/stores/device'
import type { Weekday } from '@/types/schedule'
import ScheduleEditor from '@/components/ScheduleEditor.vue'
import PageHeading from '@/components/PageHeading.vue'

const store = useDeviceStore(); const active = ref<Weekday>('mon'); const copyVisible = ref(false); const targets = ref<Weekday[]>([])
const days: { key: Weekday; label: string }[] = [{key:'mon',label:'周一'},{key:'tue',label:'周二'},{key:'wed',label:'周三'},{key:'thu',label:'周四'},{key:'fri',label:'周五'},{key:'sat',label:'周六'},{key:'sun',label:'周日'}]
async function save() {
  try {
    const result = await store.saveSchedule()
    if (result.dispatchError) {
      ElMessage.warning(`七天计划已保存，但今天当前音量下发失败：${result.dispatchError}`)
    } else if (result.currentDispatch) {
      ElMessage.success(`计划已保存，已下发今天 ${result.currentDispatch.time} 时段音量 ${result.currentDispatch.volume}`)
    } else {
      ElMessage.success('七天计划已保存，今天尚未到第一个计划时段')
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '保存计划失败')
  }
}
function copy() { store.copyDay(active.value, targets.value); copyVisible.value = false; targets.value = []; ElMessage.success('计划已复制') }
</script>
<template>
  <PageHeading title="每周音量计划" description="周一至周日分别设置时间和音量。"><div class="heading-actions"><el-button @click="copyVisible = true">复制到其它日期</el-button><el-button type="primary" @click="save">保存计划</el-button></div></PageHeading>
  <section class="card"><el-tabs v-model="active"><el-tab-pane v-for="day in days" :key="day.key" :label="day.label" :name="day.key" /></el-tabs><ScheduleEditor :slots="store.schedule[active]" :max-slots="store.maxSlotsPerDay" @change="store.schedule[active] = $event"/></section>
  <el-dialog v-model="copyVisible" title="复制计划" width="430"><p>将{{ days.find(d => d.key === active)?.label }}的计划复制到：</p><el-checkbox-group v-model="targets"><el-checkbox v-for="day in days.filter(d => d.key !== active)" :key="day.key" :value="day.key">{{ day.label }}</el-checkbox></el-checkbox-group><template #footer><el-button @click="copyVisible=false">取消</el-button><el-button type="primary" :disabled="!targets.length" @click="copy">确认复制</el-button></template></el-dialog>
</template>

<style scoped>
.heading-actions{display:flex;align-items:center;gap:10px}
</style>
