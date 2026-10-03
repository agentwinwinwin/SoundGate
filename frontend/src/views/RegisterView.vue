<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
const auth = useAuthStore(); const router = useRouter(); const loading = ref(false)
const form = reactive({ username: '', password: '', confirm: '' })
async function submit() {
  if (form.username.length < 3) return ElMessage.warning('用户名至少 3 个字符')
  if (form.password.length < 6) return ElMessage.warning('密码至少 6 个字符')
  if (form.password !== form.confirm) return ElMessage.warning('两次输入的密码不一致')
  loading.value = true
  try { await auth.register(form.username, form.password); await router.replace('/devices'); ElMessage.success('注册成功') }
  catch (error: any) { ElMessage.error(error?.response?.data?.username?.[0] || '注册失败') } finally { loading.value = false }
}
</script>
<template><main class="auth-page"><section class="auth-panel"><div class="auth-brand"><b>SoundGate</b><span>声控设备配置软件</span></div><div class="auth-form"><div><h1>创建账号</h1><p>每个账号只管理归属于自己的设备</p></div><el-form label-position="top"><el-form-item label="用户名"><el-input v-model="form.username" size="large" autocomplete="username" /></el-form-item><el-form-item label="密码"><el-input v-model="form.password" size="large" type="password" show-password autocomplete="new-password" /></el-form-item><el-form-item label="确认密码"><el-input v-model="form.confirm" size="large" type="password" show-password autocomplete="new-password" @keyup.enter="submit" /></el-form-item><el-button type="primary" size="large" :loading="loading" class="auth-submit" @click="submit">注册并登录</el-button></el-form><p class="auth-link">已有账号？<router-link to="/login">返回登录</router-link></p></div></section></main></template>
