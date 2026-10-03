import { defineStore } from 'pinia'
import type { Device } from '@/types/device'
import type { WeeklySchedule, Weekday } from '@/types/schedule'
import { deviceService } from '@/services/deviceService'
import type { NewDevice } from '@/api/devices'

const baseSlots = () => [
  { id: crypto.randomUUID(), time: '07:00', volume: 7 }, { id: crypto.randomUUID(), time: '08:00', volume: 9 },
  { id: crypto.randomUUID(), time: '15:00', volume: 5 }, { id: crypto.randomUUID(), time: '17:00', volume: 7 },
  { id: crypto.randomUUID(), time: '20:00', volume: 5 }, { id: crypto.randomUUID(), time: '23:00', volume: 2 },
]
const emptySchedule = () => Object.fromEntries(['mon','tue','wed','thu','fri','sat','sun'].map(day => [day, baseSlots()])) as WeeklySchedule

export const useDeviceStore = defineStore('device', {
  state: () => ({
    devices: [
      { id: 'SG000001', name: 'Demo Crossing A', online: true, enabled: true, volume: 7, lastSeen: '刚刚', gps: '正常', cloudConnected: true, bluetoothName: 'SoundGate-A', streetName: '示例街道A', onenetDeviceName: 'device-a' },
      { id: 'SG000002', name: 'Demo Crossing B', online: false, enabled: false, volume: 0, lastSeen: '18 分钟前', gps: '无信号', cloudConnected: false, bluetoothName: 'SoundGate-B', streetName: '示例街道B', onenetDeviceName: 'device-b' },
      { id: 'SG000003', name: 'Local Demo Device', online: true, enabled: true, volume: 5, lastSeen: '1 分钟前', gps: '正常', cloudConnected: true, bluetoothName: 'SoundGate-C', streetName: '示例街道C', onenetDeviceName: '' },
    ] as Device[],
    selectedId: localStorage.getItem('soundgate:selectedDevice') || 'SG000001',
    maxSlotsPerDay: 12,
    schedules: {} as Record<string, WeeklySchedule>,
  }),
  getters: {
    selected: (state) => state.devices.find(d => d.id === state.selectedId) ?? state.devices[0]!,
    schedule: (state): WeeklySchedule => state.schedules[state.selectedId] ?? (state.schedules[state.selectedId] = emptySchedule()),
  },
  actions: {
    select(id: string) {
      const selectedId = this.devices.some(device => device.id === id) ? id : (this.devices[0]?.id || id)
      this.selectedId = selectedId
      localStorage.setItem('soundgate:selectedDevice', selectedId)
      if (this.devices.some(device => device.id === selectedId)) void this.loadSchedule()
    },
    async loadDevices() { try { const devices = await deviceService.fetchDevices(); this.devices = devices; if (devices.length && !devices.some(device => device.id === this.selectedId)) this.select(devices[0]!.id); if (!devices.length) this.selectedId = '' } catch { /* 网络失败时保留当前数据 */ } },
    async saveSelected() { const saved = await deviceService.saveDevice(this.selected); Object.assign(this.selected, saved); return saved },
    async saveDevice(device: Device) { const saved = await deviceService.saveDevice(device); Object.assign(device, saved); return saved },
    async createDevice(device: NewDevice) { await deviceService.createDevice(device); await this.loadDevices(); this.select(device.id) },
    async importOneNETDevices(deviceNames: string[]) { const imported = await deviceService.importOneNETDevices(deviceNames); await this.loadDevices(); if (imported[0]) this.select(imported[0].id); return imported },
    async syncOneNETDevices() { const result = await deviceService.syncOneNETDevices(); await this.loadDevices(); return result },
    async deleteDevice(id: string) {
      await deviceService.deleteDevice(id)
      this.devices = this.devices.filter(device => device.id !== id)
      delete this.schedules[id]
      if (this.selectedId === id) this.select(this.devices[0]?.id || '')
    },
    async loadSchedule() { if (!this.selectedId) return; try { this.schedules[this.selectedId] = await deviceService.fetchSchedule(this.selectedId) } catch { if (!this.schedules[this.selectedId]) this.schedules[this.selectedId] = emptySchedule() } },
    async saveSchedule() {
      const result = await deviceService.saveSchedule(this.selectedId, this.schedule)
      this.schedules[this.selectedId] = result.schedule
      return result
    },
    copyDay(from: Weekday, targets: Weekday[]) { targets.forEach(day => { this.schedule[day] = this.schedule[from].map(s => ({ ...s, id: crypto.randomUUID() })) }) },
    async saveStreetName() { await deviceService.updateStreetName(this.selected.id, this.selected.streetName) },
    async renameBluetooth(name: string, password: string) { const result = await deviceService.renameBluetooth(this.selected.id, name, password); this.selected.bluetoothName = result.bluetoothName },
  },
})
