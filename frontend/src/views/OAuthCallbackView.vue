<template>
  <div class="callback-page">
    <div class="callback-card">
      <div v-if="status === 'loading'">
        <div class="spinner-lg"></div>
        <p>登入中，請稍候...</p>
      </div>
      <div v-else-if="status === 'error'">
        <div class="error-icon">❌</div>
        <p class="error-msg">{{ errorMsg }}</p>
        <RouterLink to="/login" class="btn-back">返回登入頁</RouterLink>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/api'

defineProps({
  provider: { type: String, required: true }, // 'fb' | 'ig'
})

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const status = ref('loading')
const errorMsg = ref('')

onMounted(async () => {
  const state = route.query.state
  const error = route.query.error

  if (error) {
    status.value = 'error'
    errorMsg.value = `授權失敗：${error}`
    return
  }
  if (!state) {
    status.value = 'error'
    errorMsg.value = '缺少 state 參數，請重新登入'
    return
  }

  try {
    // POST /auth/verify via Vite proxy → same origin → session cookie 正確設定
    await api.post('/auth/verify', null, { params: { state } })
    await auth.fetchMe()
    const redirect = localStorage.getItem('loginRedirect') || '/dashboard'
    localStorage.removeItem('loginRedirect')
    router.replace(redirect)
  } catch (e) {
    status.value = 'error'
    errorMsg.value = e.response?.data?.detail || '登入失敗，請重試'
  }
})
</script>

<style scoped>
.callback-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
.callback-card {
  background: #fff;
  border-radius: 20px;
  padding: 3rem 2.5rem;
  text-align: center;
  box-shadow: 0 8px 32px rgba(0,0,0,0.1);
  min-width: 280px;
}
.spinner-lg {
  width: 48px; height: 48px; margin: 0 auto 1.5rem;
  border: 4px solid #eee; border-top-color: #1877f2;
  border-radius: 50%; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.error-icon { font-size: 3rem; margin-bottom: 1rem; }
.error-msg { color: #555; margin-bottom: 1.5rem; }
.btn-back {
  display: inline-block; background: #1877f2; color: #fff;
  text-decoration: none; padding: 10px 20px; border-radius: 10px;
  font-weight: 600;
}
</style>
