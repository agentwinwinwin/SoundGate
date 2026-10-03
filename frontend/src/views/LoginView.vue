<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore(); const router = useRouter(); const route = useRoute(); const loading = ref(false)
const form = reactive({ username: 'admin', password: '123456' })
async function submit() {
  if (!form.username || !form.password) return ElMessage.warning('请输入用户名和密码')
  loading.value = true
  try { await auth.login(form.username, form.password); await router.replace(String(route.query.redirect || '/devices')); ElMessage.success('登录成功') }
  catch { ElMessage.error('用户名或密码错误') } finally { loading.value = false }
}
</script>
<template><main class="auth-page"><section class="auth-panel"><div class="auth-brand"><b>SoundGate</b><span>声控设备配置软件</span></div><div class="auth-form"><div><h1>欢迎回来</h1><p>登录后管理账号下的 SoundGate 设备</p></div><el-form label-position="top" @submit.prevent="submit"><el-form-item label="用户名"><el-input v-model="form.username" size="large" autocomplete="username" @keyup.enter="submit" /></el-form-item><el-form-item label="密码"><el-input v-model="form.password" size="large" type="password" show-password autocomplete="current-password" @keyup.enter="submit" /></el-form-item><el-button type="primary" size="large" :loading="loading" class="auth-submit" @click="submit">登录</el-button></el-form><p class="auth-link">还没有账号？<router-link to="/register">立即注册</router-link></p><div class="demo-account">测试管理员：<b>admin</b> / <b>123456</b></div></div></section></main></template>
