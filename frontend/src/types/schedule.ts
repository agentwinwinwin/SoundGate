export type Weekday = 'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun'
export interface TimeSlot { id: string; time: string; volume: number }
export type WeeklySchedule = Record<Weekday, TimeSlot[]>
