<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { TimeSlot } from '@/types/schedule'

const props = defineProps<{ slots: TimeSlot[]; maxSlots: number }>()
const emit = defineEmits<{ change: [slots: TimeSlot[]] }>()
const editingId = ref<string>(); const form = reactive({ time: '07:00', volume: 5 })
const sorted = computed(() => [...props.slots].sort((a,b) => a.time.localeCompare(b.time)))
watch(() => props.slots, () => { editingId.value = undefined }, { deep: false })
function add() { if (props.slots.length >= props.maxSlots) return ElMessage.warning(`每日最多 ${props.maxSlots} 个时段`); editingId.value = ''; form.time = '07:00'; form.volume = 5 }
function edit(slot: TimeSlot) { editingId.value = slot.id; form.time = slot.time; form.volume = slot.volume }
function submit() {
  if (props.slots.some(s => s.time === form.time && s.id !== editingId.value)) return ElMessage.warning('该时间已存在')
  const next = editingId.value ? props.slots.map(s => s.id === editingId.value ? { ...s, ...form } : s) : [...props.slots, { id: crypto.randomUUID(), ...form }]
  emit('change', next); editingId.value = undefined
}
async function remove(id: string) { await ElMessageBox.confirm('确定删除这个时段吗？', '删除时段', { type: 'warning' }); emit('change', props.slots.filter(s => s.id !== id)) }
</script>
<template>
  <div class="schedule-layout">
    <div><el-table :data="sorted"><el-table-column prop="time" label="时间" width="130"/><el-table-column label="音量"><template #default="{ row }"><div class="volume-preview"><b>{{ row.volume }}</b><el-progress :percentage="row.volume / 9 * 100" :show-text="false" /></div></template></el-table-column><el-table-column label="操作" width="150"><template #default="{ row }"><el-button link type="primary" @click="edit(row)">编辑</el-button><el-button link type="danger" @click="remove(row.id)">删除</el-button></template></el-table-column></el-table><div class="table-actions"><span>{{ slots.length }} / {{ maxSlots }} 个时段</span><el-button type="primary" plain @click="add">＋ 添加时段</el-button></div></div>
    <div class="editor-panel"><h3>{{ editingId === '' ? '添加时段' : editingId ? '编辑时段' : '选择一个时段' }}</h3><template v-if="editingId !== undefined"><el-form label-position="top"><el-form-item label="时间"><el-time-select v-model="form.time" start="00:00" step="00:15" end="23:45" /></el-form-item><el-form-item label="音量 0~9"><el-input-number v-model="form.volume" :min="0" :max="9" /></el-form-item><el-button type="primary" @click="submit">{{ editingId ? '更新' : '添加' }}</el-button><el-button @click="editingId = undefined">取消</el-button></el-form></template><p v-else class="muted">点击列表中的“编辑”，或添加新时段。</p></div>
  </div>
</template>
