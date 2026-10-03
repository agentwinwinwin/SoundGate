export interface Device {
  id: string
  name: string
  online: boolean
  enabled: boolean
  volume: number
  lastSeen: string
  gps: '正常' | '异常' | '无信号'
  cloudConnected: boolean
  bluetoothName: string
  streetName: string
  onenetDeviceName: string
}

export interface AudioValidation {
  valid: boolean
  fileName: string
  channels?: number
  sampleRate?: number
  bitDepth?: number
  duration?: number
  errors: string[]
}
