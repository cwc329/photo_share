import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/api'

export const useAuthStore = defineStore('auth', () => {
  const fbUser = ref(null)      // { id, name, pages: [...] }
  const igAccounts = ref([])    // [{ id, ig_user_id, username, name, token_expires_at }]
  const loading = ref(false)

  const isLoggedIn = computed(() => fbUser.value !== null || igAccounts.value.length > 0)
  const pages = computed(() => fbUser.value?.pages ?? [])

  async function fetchMe() {
    loading.value = true
    try {
      const { data } = await api.get('/auth/me')
      fbUser.value = data.fb_user ?? null
      igAccounts.value = data.ig_accounts ?? []
    } catch {
      fbUser.value = null
      igAccounts.value = []
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    await api.post('/auth/logout')
    fbUser.value = null
    igAccounts.value = []
  }

  return { fbUser, igAccounts, loading, isLoggedIn, pages, fetchMe, logout }
})
