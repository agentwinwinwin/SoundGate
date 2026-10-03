import { defineStore } from 'pinia'
import { apiClient } from '@/api/devices'

type AuthResponse = { token: string; username: string }

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('soundgate:token') || '',
    username: localStorage.getItem('soundgate:username') || '',
  }),
  getters: { authenticated: state => Boolean(state.token) },
  actions: {
    persist(data: AuthResponse) {
      this.token = data.token; this.username = data.username
      localStorage.setItem('soundgate:token', data.token)
      localStorage.setItem('soundgate:username', data.username)
    },
    async login(username: string, password: string) { const { data } = await apiClient.post<AuthResponse>('/auth/login/', { username, password }); this.persist(data) },
    async register(username: string, password: string) { const { data } = await apiClient.post<AuthResponse>('/auth/register/', { username, password }); this.persist(data) },
    async logout() {
      try { await apiClient.post('/auth/logout/') } finally {
        this.token = ''; this.username = ''
        localStorage.removeItem('soundgate:token'); localStorage.removeItem('soundgate:username'); localStorage.removeItem('soundgate:selectedDevice')
      }
    },
  },
})
