<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeading from '@/components/PageHeading.vue'
import AudioUploader from '@/components/AudioUploader.vue'
import { useDeviceStore } from '@/stores/device'
import { createFileTransfer, fetchCommand, fetchFileTransfer, playAudio, stopAudio, uploadAudioFile } from '@/api/devices'
import type { FileTransfer } from '@/api/devices'
const store = useDeviceStore()
const uploading = ref<string>()
const commandBusy = ref(false)
const transfers = ref<Partial<Record<'walk' | 'rush' | 'custom', FileTransfer>>>({})
function preview() { if ('speechSynthesis' in window) { speechSynthesis.cancel(); speechSynthesis.speak(new SpeechSynthesisUtterance(store.selected.streetName)) } else ElMessage.info('当前浏览器不支持语音试听') }
async function save() { try { await store.saveStreetName(); ElMessage.warning(`已保存 ${store.selected.name} 的街道名称；尚未同步到终端`) } catch { ElMessage.error('保存失败，请确认 DRF 后端已启动') } }
async function upload(kind: 'walk' | 'rush' | 'custom', file: File) {
  uploading.value = kind
  try {
    const result = await uploadAudioFile(store.selected.id, kind, file)
    const transfer = await createFileTransfer(store.selected.id, result.file.id); transfers.value[kind] = transfer
    ElMessage.success(`${file.name} 已通过服务端校验，传输任务 ${transfer.transferId} 已排队`)
    for (let i = 0; i < 30 && !['succeeded','failed','cancelled'].includes(transfers.value[kind]?.status || ''); i++) {
      await new Promise(resolve => setTimeout(resolve, 1000))
      transfers.value[kind] = await fetchFileTransfer(store.selected.id, transfer.transferId)
    }
  } catch (error: any) { ElMessage.error(error?.response?.data?.detail || '服务端音频校验失败') }
  finally { uploading.value = undefined }
}
async function testPlay(kind: 'walk' | 'rush' | 'custom') {
  commandBusy.value = true
  try { const command = await playAudio(store.selected.id, kind); await waitForCommand(command.requestId, '试听') }
  catch (error: any) { ElMessage.error(error?.response?.data?.detail || '试听命令提交失败') }
  finally { commandBusy.value = false }
}
async function testStop() {
  commandBusy.value = true
  try { const command = await stopAudio(store.selected.id); await waitForCommand(command.requestId, '停止试听') }
  catch (error: any) { ElMessage.error(error?.response?.data?.detail || '停止命令提交失败') }
  finally { commandBusy.value = false }
}
async function waitForCommand(requestId: string, label: string) {
  ElMessage.info(`${label}命令已发送，正在等待终端响应`)
  for (let i = 0; i < 30; i++) {
    await new Promise(resolve => setTimeout(resolve, 1000))
    const command = await fetchCommand(store.selected.id, requestId)
    if (command.status === 'succeeded') return ElMessage.success(`${label}已由终端确认`)
    if (command.status === 'failed') throw new Error(command.error || '终端响应失败')
  }
  ElMessage.warning(`${label}仍在等待终端响应，可稍后重试`)
}
</script>
<template>
  <PageHeading title="街道语音 / 提示音" description="设置街道播报内容，并在本地校验设备声音文件。"><el-button type="primary" @click="save">保存</el-button></PageHeading>
  <div class="audio-page">
    <section class="card"><div class="card-title"><div><h3>街道语音</h3><p>当前设备：{{ store.selected.name }}（{{ store.selected.id }}）</p></div></div><el-form-item label="街道名称"><el-input v-model="store.selected.streetName" placeholder="请输入该设备所在的街道名称" /></el-form-item><div class="right"><el-button type="primary" plain @click="preview">▶ 试听</el-button></div></section>
    <section class="card"><div class="audio-rule"><b>音频规范</b><span>WAV / 单声道 / 8kHz / 8bit / 全部内容总长度 ≤ 32 秒</span><div class="timeline"><i>慢行 4s</i><i>快行 4s</i><i>客户定制 24s</i></div></div><AudioUploader label="慢行提示音" :max-duration="4" @validated="upload('walk', $event)"/><p v-if="transfers.walk" class="muted">慢行传输：{{ transfers.walk.status }} · {{ transfers.walk.progress }}%</p><AudioUploader label="快行提示音" :max-duration="4" @validated="upload('rush', $event)"/><p v-if="transfers.rush" class="muted">快行传输：{{ transfers.rush.status }} · {{ transfers.rush.progress }}%</p><AudioUploader label="客户定制音频" :max-duration="24" @validated="upload('custom', $event)"/><p v-if="transfers.custom" class="muted">定制音频传输：{{ transfers.custom.status }} · {{ transfers.custom.progress }}%</p><p v-if="uploading" class="muted">正在由服务端复验并创建传输任务…</p><div class="right"><el-button :disabled="commandBusy" @click="testPlay('walk')">试听慢行</el-button><el-button :disabled="commandBusy" @click="testPlay('rush')">试听快行</el-button><el-button :disabled="commandBusy" @click="testPlay('custom')">试听定制</el-button><el-button type="danger" plain :loading="commandBusy" @click="testStop">停止试听</el-button></div></section>
  </div>
</template>
