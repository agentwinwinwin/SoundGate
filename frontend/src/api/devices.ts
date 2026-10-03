import axios from 'axios'
import type { Device } from '@/types/device'
import type { WeeklySchedule, Weekday } from '@/types/schedule'

export const apiClient = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL || '/api', timeout: 5000 })
apiClient.interceptors.request.use(config => {
  const token = localStorage.getItem('soundgate:token')
  if (token) config.headers.Authorization = `Token ${token}`
  return config
})
const wait = (ms = 220) => new Promise((resolve) => setTimeout(resolve, ms))

export async function mockSaveDevice(device: Device) { await wait(); return structuredClone(device) }
export async function mockSaveSchedule(schedule: WeeklySchedule) { await wait(); return structuredClone(schedule) }
export async function mockRenameBluetooth(name: string, password: string) {
  await wait()
  if (!password.trim()) throw new Error('请输入管理密码')
  return { bluetoothName: name }
}

export async function fetchDevices() { return (await apiClient.get<Device[]>('/devices/')).data }
export type NewDevice = { id: string; name: string; bluetoothName: string; streetName: string; onenetDeviceName: string }
export async function createDevice(device: NewDevice) { await apiClient.post('/devices/', device) }
export type OneNETDevice = { deviceName: string; online: boolean; added: boolean; claimed: boolean }
export async function fetchOneNETDevices() { return (await apiClient.get<{ devices: OneNETDevice[]; total: number }>('/devices/onenet/available/')).data }
export async function importOneNETDevices(deviceNames: string[]) { return (await apiClient.post<Device[]>('/devices/onenet/import/', { deviceNames })).data }
export async function syncOneNETDevices() { return (await apiClient.post<{ synced: unknown[]; errors: unknown[] }>('/devices/onenet/sync/')).data }
export async function updateDevice(device: Device) { return (await apiClient.patch<Device>(`/devices/${device.id}/`, { name: device.name, enabled: device.enabled, volume: device.volume })).data }
export async function deleteDevice(id: string) { await apiClient.delete(`/devices/${id}/`) }
export type LocalDeliveryResult = { delivery: 'local_only' | 'pending_terminal_protocol'; terminalConfirmed: false }
export async function updateStreetName(id: string, streetName: string) { return (await apiClient.patch<LocalDeliveryResult & { streetName: string }>(`/devices/${id}/audio-config/`, { streetName })).data }
export async function renameBluetooth(id: string, bluetoothName: string, password: string) { return (await apiClient.post<LocalDeliveryResult & { bluetoothName: string; accepted: true }>(`/devices/${id}/rename-bluetooth/`, { bluetoothName, password })).data }
export type OneNETParameters = {
  DftEdMinute: number; DftEnable: number; DftStHour: number; DftStMinute: number
  DftVolume: number; DtfEdHour: number; Period: number; RushTime: number; WalkTime: number
}
export type OneNETParameterState = { value: number | string | null; displayValue: number | string | null; name: string; dataType: string }
export async function fetchOneNETParameters(id: string, keys?: (keyof OneNETParameters)[]) {
  return (await apiClient.get<{ parameters: Partial<Record<keyof OneNETParameters, OneNETParameterState>> }>(`/devices/${id}/onenet/parameters/`, { params: keys?.length ? { keys: keys.join(',') } : undefined, timeout: 30000 })).data.parameters
}
export async function updateOneNETParameters(id: string, parameters: Partial<OneNETParameters>) {
  return (await apiClient.post(`/devices/${id}/onenet/parameters/`, parameters, { timeout: 30000 })).data
}
const dayNumber: Record<Weekday, number> = { mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6, sun: 7 }
const numberDay = Object.fromEntries(Object.entries(dayNumber).map(([day, number]) => [number, day])) as Record<number, Weekday>
type ApiSlot = { id: number; weekday: number; time: string; volume: number }
export async function fetchSchedule(id: string): Promise<WeeklySchedule> {
  const { slots } = (await apiClient.get<{ slots: ApiSlot[] }>(`/devices/${id}/schedule/`)).data
  const result = Object.fromEntries(Object.keys(dayNumber).map(day => [day, []])) as unknown as WeeklySchedule
  slots.forEach(slot => result[numberDay[slot.weekday]].push({ id: String(slot.id), time: slot.time, volume: slot.volume }))
  return result
}
export type ScheduleDispatchResult = {
  schedule: WeeklySchedule
  currentDispatch: { weekday: number; time: string; volume: number; transport: string } | null
  dispatchError: string | null
}
export async function saveSchedule(id: string, schedule: WeeklySchedule): Promise<ScheduleDispatchResult> {
  const slots = Object.entries(schedule).flatMap(([day, values]) => values.map(slot => ({ weekday: dayNumber[day as Weekday], time: slot.time, volume: slot.volume })))
  const response = await apiClient.put<{ slots: ApiSlot[]; currentDispatch: ScheduleDispatchResult['currentDispatch']; dispatchError: string | null }>(`/devices/${id}/schedule/`, { slots })
  const saved = Object.fromEntries(Object.keys(dayNumber).map(day => [day, []])) as unknown as WeeklySchedule
  response.data.slots.forEach(slot => saved[numberDay[slot.weekday]].push({ id: String(slot.id), time: slot.time, volume: slot.volume }))
  return { schedule: saved, currentDispatch: response.data.currentDispatch, dispatchError: response.data.dispatchError }
}
