<script setup lang="ts">
import { ref } from 'vue'
import { UploadFilled, CircleCheckFilled, CircleCloseFilled } from '@element-plus/icons-vue'
import type { AudioValidation } from '@/types/device'

const props = defineProps<{ label: string; maxDuration: number }>()
const result = ref<AudioValidation>()
async function choose(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]; if (!file) return
  const errors: string[] = []
  if (!file.name.toLowerCase().endsWith('.wav')) errors.push('文件必须为 WAV 格式')
  let channels: number | undefined, sampleRate: number | undefined, bitDepth: number | undefined, duration: number | undefined
  try {
    const buffer = await file.arrayBuffer(); const view = new DataView(buffer)
    const text = (start: number, len: number) => Array.from({length: len}, (_,i) => String.fromCharCode(view.getUint8(start+i))).join('')
    if (buffer.byteLength < 44 || text(0,4) !== 'RIFF' || text(8,4) !== 'WAVE') throw new Error()
    let pos = 12; let dataSize = 0; let byteRate = 0
    while (pos + 8 <= view.byteLength) { const id = text(pos,4); const size = view.getUint32(pos+4,true); if (id === 'fmt ') { channels=view.getUint16(pos+10,true); sampleRate=view.getUint32(pos+12,true); byteRate=view.getUint32(pos+16,true); bitDepth=view.getUint16(pos+22,true) } if (id === 'data') dataSize=size; pos += 8 + size + (size % 2) }
    if (byteRate && dataSize) duration = dataSize / byteRate
  } catch { errors.push('无法读取 WAV 文件头') }
  if (channels !== undefined && channels !== 1) errors.push('必须为单声道')
  if (sampleRate !== undefined && sampleRate !== 8000) errors.push('采样率必须为 8kHz')
  if (bitDepth !== undefined && bitDepth !== 8) errors.push('位深必须为 8bit')
  if (duration !== undefined && duration > props.maxDuration + .05) errors.push(`时长不能超过 ${props.maxDuration} 秒`)
  result.value = { valid: errors.length === 0, fileName: file.name, channels, sampleRate, bitDepth, duration, errors }
}
</script>
<template>
  <div class="audio-upload">
    <label><el-icon :size="25"><UploadFilled /></el-icon><b>{{ label }}：选择 WAV 文件</b><small>单声道 · 8kHz · 8bit · ≤ {{ maxDuration }} 秒</small><input type="file" accept=".wav,audio/wav" @change="choose"></label>
    <div v-if="result" class="validation" :class="result.valid ? 'valid' : 'invalid'"><el-icon><CircleCheckFilled v-if="result.valid"/><CircleCloseFilled v-else/></el-icon><div><b>{{ result.fileName }}</b><span v-if="result.channels">{{ result.channels }} 声道 · {{ result.sampleRate }}Hz · {{ result.bitDepth }}bit · {{ result.duration?.toFixed(2) }} 秒</span><span v-for="error in result.errors" :key="error">{{ error }}</span></div></div>
  </div>
</template>
