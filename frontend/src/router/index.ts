import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/devices' },
    { path: '/login', name: '登录', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
    { path: '/register', name: '注册', component: () => import('@/views/RegisterView.vue'), meta: { public: true } },
    { path: '/devices', name: '设备管理', component: () => import('@/views/DeviceListView.vue') },
    { path: '/devices/:id', name: '设备详情', component: () => import('@/views/DeviceDetailView.vue') },
    { path: '/devices/:id/schedule', name: '每周音量计划', component: () => import('@/views/WeeklyScheduleView.vue') },
    { path: '/devices/:id/audio', name: '街道语音 / 提示音', component: () => import('@/views/AudioSettingsView.vue') },
    { path: '/devices/:id/settings', name: '设备设置', component: () => import('@/views/DeviceSettingsView.vue') },
  ],
})

router.beforeEach((to) => {
  const loggedIn = Boolean(localStorage.getItem('soundgate:token'))
  if (!to.meta.public && !loggedIn) return { path: '/login', query: { redirect: to.fullPath } }
  if (to.meta.public && loggedIn) return '/devices'
})

export default router
