<script setup lang="ts">
import { ElMessage } from 'element-plus'
import PageHeading from '@/components/PageHeading.vue'
import AudioUploader from '@/components/AudioUploader.vue'
import { useDeviceStore } from '@/stores/device'
const store = useDeviceStore()
function preview() { if ('speechSynthesis' in window) { speechSynthesis.cancel(); speechSynthesis.speak(new SpeechSynthesisUtterance(store.selected.streetName)) } else ElMessage.info('当前浏览器不支持语音试听') }
async function save() { try { await store.saveStreetName(); ElMessage.warning(`已保存 ${store.selected.name} 的街道名称；尚未同步到终端`) } catch { ElMessage.error('保存失败，请确认 DRF 后端已启动') } }
</script>
<template>
  <PageHeading title="街道语音 / 提示音" description="设置街道播报内容，并在本地校验设备声音文件。"><el-button type="primary" @click="save">保存</el-button></PageHeading>
  <div class="audio-page">
    <section class="card"><div class="card-title"><div><h3>街道语音</h3><p>当前设备：{{ store.selected.name }}（{{ store.selected.id }}）</p></div></div><el-form-item label="街道名称"><el-input v-model="store.selected.streetName" placeholder="请输入该设备所在的街道名称" /></el-form-item><div class="right"><el-button type="primary" plain @click="preview">▶ 试听</el-button></div></section>
    <section class="card"><div class="audio-rule"><b>音频规范</b><span>WAV / 单声道 / 8kHz / 8bit / 全部内容总长度 ≤ 32 秒</span><div class="timeline"><i>慢行 4s</i><i>快行 4s</i><i>客户定制 24s</i></div></div><AudioUploader label="慢行提示音" :max-duration="4"/><AudioUploader label="快行提示音" :max-duration="4"/><AudioUploader label="客户定制音频" :max-duration="24"/></section>
  </div>
</template>
