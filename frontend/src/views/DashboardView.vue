<template>
  <div class="dashboard">
    <div class="page-header">
      <h2>Dashboard</h2>
      <RouterLink to="/publish" class="btn-primary">+ 新增發佈</RouterLink>
    </div>

    <!-- Facebook Pages -->
    <section class="card" v-if="auth.pages.length > 0">
      <h3 class="card-title">
        <span class="card-title-icon">📘</span> Facebook Pages
      </h3>
      <div class="pages-grid">
        <div v-for="page in auth.pages" :key="page.id" class="page-card">
          <div class="page-info">
            <div class="page-avatar fb-avatar">{{ page.page_name[0] }}</div>
            <div>
              <div class="page-name">{{ page.page_name }}</div>
              <div class="page-meta">Facebook Page</div>
            </div>
          </div>
          <div v-if="page.ig_account_name" class="ig-badge">
            <span class="ig-dot"></span>
            @{{ page.ig_account_name }}
          </div>
          <div v-else class="ig-badge ig-none">未連結 Instagram</div>
        </div>
      </div>
    </section>

    <!-- Instagram Accounts (direct login) -->
    <section class="card" v-if="auth.igAccounts.length > 0">
      <h3 class="card-title">
        <span class="card-title-icon">📷</span> Instagram 帳號
      </h3>
      <div class="pages-grid">
        <div v-for="acc in auth.igAccounts" :key="acc.id" class="page-card">
          <div class="page-info">
            <div class="page-avatar ig-avatar">{{ acc.username[0].toUpperCase() }}</div>
            <div>
              <div class="page-name">@{{ acc.username }}</div>
              <div class="page-meta">{{ acc.name || 'Instagram 專業帳號' }}</div>
            </div>
          </div>
          <div class="token-expiry" :class="{ expiring: isExpiringSoon(acc.token_expires_at) }">
            Token 效期：{{ formatExpiry(acc.token_expires_at) }}
          </div>
        </div>
      </div>
    </section>

    <!-- No accounts -->
    <section class="card" v-if="auth.pages.length === 0 && auth.igAccounts.length === 0">
      <div class="empty-state">尚無連結帳號，請先登入</div>
    </section>

    <!-- Scheduled Posts -->
    <section class="card">
      <h3 class="card-title">
        <span class="card-title-icon">📅</span> 排程列表
      </h3>
      <div v-if="postsLoading" class="loading">載入中...</div>
      <div v-else-if="posts.length === 0" class="empty-state">尚無排程發佈</div>
      <div v-else class="posts-list">
        <div v-for="post in posts" :key="post.id" class="post-item">
          <img :src="apiBase + '/uploads/' + post.image_path" class="post-thumb" />
          <div class="post-info">
            <p class="post-caption">{{ post.caption }}</p>
            <div class="post-meta">
              <span class="platform-badge" v-for="p in post.platforms" :key="p">
                {{ p === 'facebook' ? '📘 FB' : '📷 IG' }}
              </span>
              <span class="scheduled-time">{{ formatDate(post.scheduled_at) }}</span>
            </div>
            <p v-if="post.error_message" class="post-error">{{ post.error_message }}</p>
          </div>
          <span class="status-badge" :class="post.status">{{ statusLabel(post.status) }}</span>
          <button
            v-if="post.status === 'pending'"
            class="btn-cancel"
            @click="cancelPost(post.id)"
          >取消</button>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import api from '@/api'

const auth = useAuthStore()
const posts = ref([])
const postsLoading = ref(false)
const apiBase = import.meta.env.VITE_API_BASE_URL

const statusLabel = (s) => ({ pending: '待發佈', published: '已發佈', failed: '失敗', cancelled: '已取消' }[s] || s)

const userTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone
function getLocalOffsetLabel(d = new Date()) {
  const parts = new Intl.DateTimeFormat('zh-TW', { timeZoneName: 'shortOffset' }).formatToParts(d)
  return parts.find((p) => p.type === 'timeZoneName')?.value || 'GMT'
}

function parseUtcLike(dt) {
  // 後端若回傳無時區資訊的 ISO（例如 2026-04-23T10:00:00），其語意通常是 UTC。
  // JS 對「無時區」字串會視為 local time，導致畫面顯示少了時區轉換。
  if (!dt) return null
  if (dt instanceof Date) return dt
  if (typeof dt !== 'string') return new Date(dt)
  const hasTz = /([zZ]|[+-]\d{2}:\d{2})$/.test(dt)
  return new Date(hasTz ? dt : `${dt}Z`)
}

function formatDate(dt) {
  const d = parseUtcLike(dt)
  if (!d || Number.isNaN(d.getTime())) return String(dt ?? '')
  const local = d.toLocaleString('zh-TW', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
  return `${local}（${getLocalOffsetLabel(d)} ${userTimeZone}）`
}

function formatExpiry(dt) {
  if (!dt) return '未知'
  const d = new Date(dt)
  const days = Math.floor((d - Date.now()) / 86400000)
  if (days < 0) return '已過期'
  if (days === 0) return '今天到期'
  return `${days} 天後`
}

function isExpiringSoon(dt) {
  if (!dt) return false
  const days = Math.floor((new Date(dt) - Date.now()) / 86400000)
  return days <= 7
}

async function loadPosts() {
  postsLoading.value = true
  try {
    const { data } = await api.get('/posts')
    posts.value = data
  } finally {
    postsLoading.value = false
  }
}

async function cancelPost(id) {
  if (!confirm('確定要取消這則排程？')) return
  await api.delete(`/posts/${id}`)
  await loadPosts()
}

onMounted(loadPosts)
</script>

<style scoped>
.dashboard { display: flex; flex-direction: column; gap: 1.5rem; }
.page-header { display: flex; align-items: center; justify-content: space-between; }
.page-header h2 { font-size: 1.5rem; font-weight: 700; }

.btn-primary {
  background: #1877f2; color: #fff; text-decoration: none;
  padding: 10px 20px; border-radius: 10px; font-weight: 600; font-size: 0.9rem;
  transition: background 0.15s;
}
.btn-primary:hover { background: #166fe5; }

.card { background: #fff; border-radius: 16px; padding: 1.5rem; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
.card-title { font-size: 1rem; font-weight: 600; margin-bottom: 1rem; color: #333; display: flex; align-items: center; gap: 6px; }
.card-title-icon { font-size: 1.1rem; }

.empty-state { color: #999; font-size: 0.9rem; padding: 0.5rem 0; }
.loading { color: #999; font-size: 0.9rem; }

.pages-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 1rem; }
.page-card { border: 1px solid #eee; border-radius: 12px; padding: 1rem; }
.page-info { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem; }
.page-avatar {
  width: 40px; height: 40px; border-radius: 50%;
  color: #fff; display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 1.1rem; flex-shrink: 0;
}
.fb-avatar { background: #1877f2; }
.ig-avatar { background: linear-gradient(135deg, #f58529, #dd2a7b); }

.page-name { font-weight: 600; font-size: 0.95rem; }
.page-meta { font-size: 0.78rem; color: #888; }
.ig-badge { font-size: 0.82rem; color: #c13584; display: flex; align-items: center; gap: 4px; }
.ig-dot { width: 8px; height: 8px; background: #c13584; border-radius: 50%; }
.ig-none { color: #bbb; }
.token-expiry { font-size: 0.78rem; color: #888; }
.token-expiry.expiring { color: #e07b00; font-weight: 600; }

.posts-list { display: flex; flex-direction: column; gap: 0.75rem; }
.post-item {
  display: flex; align-items: center; gap: 1rem;
  border: 1px solid #eee; border-radius: 12px; padding: 0.75rem;
}
.post-thumb { width: 64px; height: 64px; object-fit: cover; border-radius: 8px; flex-shrink: 0; }
.post-info { flex: 1; min-width: 0; }
.post-caption { font-size: 0.88rem; color: #333; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.post-meta { display: flex; align-items: center; gap: 0.5rem; margin-top: 0.3rem; flex-wrap: wrap; }
.platform-badge { font-size: 0.78rem; background: #f0f2f5; padding: 2px 8px; border-radius: 20px; }
.scheduled-time { font-size: 0.78rem; color: #888; }
.post-error { font-size: 0.78rem; color: #e53935; margin-top: 0.2rem; }

.status-badge { font-size: 0.78rem; padding: 4px 10px; border-radius: 20px; font-weight: 600; flex-shrink: 0; }
.status-badge.pending { background: #fff3cd; color: #856404; }
.status-badge.published { background: #d1e7dd; color: #0f5132; }
.status-badge.failed { background: #f8d7da; color: #842029; }
.status-badge.cancelled { background: #e2e3e5; color: #555; }

.btn-cancel {
  background: none; border: 1px solid #ddd; border-radius: 8px;
  padding: 5px 10px; font-size: 0.8rem; cursor: pointer; color: #666; flex-shrink: 0;
}
.btn-cancel:hover { border-color: #e53935; color: #e53935; }
</style>
