<template>
  <div class="publish-view">
    <div class="page-header">
      <RouterLink to="/dashboard" class="back-link">← 返回</RouterLink>
      <h2>建立發佈</h2>
    </div>

    <form class="publish-form" @submit.prevent="submitPost">
      <div class="form-layout">
        <!-- Left: Image + Hashtags -->
        <div class="col-left">
          <div class="form-section">
            <label class="form-label">選擇圖片</label>
            <PhotoUpload :key="photoUploadKey" @uploaded="onImageUploaded" />
          </div>

          <div class="form-section" v-if="hashtagSuggestions">
            <label class="form-label">Hashtag 建議（來自 EXIF）</label>
            <HashtagPicker
              :suggestions="hashtagSuggestions"
              @update:selected-tags="onHashtagsSelected"
            />
          </div>
        </div>

        <!-- Right: Account, Platform, Caption, Schedule -->
        <div class="col-right">

          <!-- Account selector -->
          <div class="form-section">
            <label class="form-label">選擇帳號</label>
            <div class="account-tabs" v-if="hasBothTypes">
              <button type="button" :class="['acct-tab', { active: accountType === 'fb' }]" @click="setAccountType('fb')">
                📘 Facebook Page
              </button>
              <button type="button" :class="['acct-tab', { active: accountType === 'ig' }]" @click="setAccountType('ig')">
                📷 Instagram
              </button>
            </div>

            <select v-if="accountType === 'fb'" class="form-select" v-model="selectedPageId" required>
              <option value="" disabled>請選擇 Facebook Page</option>
              <option v-for="page in auth.pages" :key="page.id" :value="page.id">
                {{ page.page_name }}
                {{ page.ig_account_name ? `（IG: @${page.ig_account_name}）` : '' }}
              </option>
            </select>

            <select v-if="accountType === 'ig'" class="form-select" v-model="selectedIgId" required>
              <option value="" disabled>請選擇 Instagram 帳號</option>
              <option v-for="acc in auth.igAccounts" :key="acc.id" :value="acc.id">
                @{{ acc.username }}{{ acc.name ? ` (${acc.name})` : '' }}
              </option>
            </select>
          </div>

          <!-- Platform selector -->
          <div class="form-section">
            <label class="form-label">發佈平台</label>
            <PlatformSelector
              v-model="selectedPlatforms"
              :account-type="accountType"
              :selected-page="selectedPage"
            />
          </div>

          <!-- Caption -->
          <div class="form-section">
            <label class="form-label">
              文案
              <span class="char-count">{{ caption.length }} 字</span>
            </label>
            <textarea
              class="form-textarea"
              v-model="caption"
              placeholder="輸入發文文案..."
              rows="5"
              required
            ></textarea>
            <div v-if="selectedHashtags.length > 0" class="hashtag-preview">
              <button type="button" class="btn-append-tags" @click="appendHashtags">
                + 將 {{ selectedHashtags.length }} 個 hashtag 加入文案
              </button>
            </div>
          </div>

          <!-- Schedule -->
          <div class="form-section">
            <label class="form-label">發佈時間</label>
            <SchedulePicker
              ref="schedulePicker"
              @update:scheduledAt="scheduledAt = $event"
              @update:mode="scheduleMode = $event"
            />
          </div>

          <div v-if="submitError" class="submit-error">{{ submitError }}</div>

          <button
            type="submit"
            class="btn-submit"
            :disabled="submitting || !canSubmit"
          >
            <span v-if="submitting" class="spinner"></span>
            {{ submitting ? '送出中...' : '確認發佈' }}
          </button>
        </div>
      </div>
    </form>

    <!-- Success Modal -->
    <div v-if="showSuccess" class="modal-overlay" @click.self="showSuccess = false">
      <div class="modal-card">
        <div class="modal-icon">✅</div>
        <h3>發佈任務已建立</h3>
        <p>已成功排程，將在指定時間自動發佈。</p>
        <div class="modal-actions">
          <RouterLink to="/dashboard" class="btn-primary">查看排程列表</RouterLink>
          <button class="btn-secondary" @click="resetForm">繼續新增</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import api from '@/api'
import PhotoUpload from '@/components/PhotoUpload.vue'
import HashtagPicker from '@/components/HashtagPicker.vue'
import PlatformSelector from '@/components/PlatformSelector.vue'
import SchedulePicker from '@/components/SchedulePicker.vue'

const schedulePicker = ref(null)
const photoUploadKey = ref(0)

const auth = useAuthStore()

// Determine which account types the user has
const hasFb = computed(() => auth.pages.length > 0)
const hasIg = computed(() => auth.igAccounts.length > 0)
const hasBothTypes = computed(() => hasFb.value && hasIg.value)

// Default to whichever type the user has
const accountType = ref(hasFb.value ? 'fb' : 'ig')

function setAccountType(type) {
  accountType.value = type
  selectedPageId.value = ''
  selectedIgId.value = ''
  selectedPlatforms.value = []
}

const selectedPageId = ref('')
const selectedIgId = ref('')
const selectedPlatforms = ref([])
const caption = ref('')
const scheduledAt = ref(null)
/** 僅存在於瀏覽器，送出 /posts 時才上傳並寫入伺服器 */
const pendingImageFile = ref(null)
const hashtagSuggestions = ref(null)
const selectedHashtags = ref([])
const submitting = ref(false)
const submitError = ref('')
const showSuccess = ref(false)

const selectedPage = computed(() =>
  auth.pages.find((p) => p.id === selectedPageId.value) || null
)

// 追蹤 SchedulePicker 的 mode（預設 'now'，與 SchedulePicker 初始值一致）
const scheduleMode = ref('now')

const canSubmit = computed(() => {
  const hasAccount = accountType.value === 'fb' ? !!selectedPageId.value : !!selectedIgId.value
  // 立即發佈 mode：scheduledAt 為 null（送出時才計算），仍視為有效
  const hasSchedule = scheduleMode.value === 'now' || !!scheduledAt.value
  return (
    !!pendingImageFile.value &&
    hasAccount &&
    selectedPlatforms.value.length > 0 &&
    hasSchedule
  )
})

function onImageUploaded(data) {
  pendingImageFile.value = data.file
  hashtagSuggestions.value = data.hashtag_suggestions
  selectedHashtags.value = []
}

function onHashtagsSelected(tags) {
  selectedHashtags.value = tags
}

function appendHashtags() {
  const tagStr = selectedHashtags.value.join(' ')
  if (caption.value && !caption.value.endsWith('\n')) caption.value += '\n'
  caption.value += tagStr
  selectedHashtags.value = []
}

async function submitPost() {
  submitError.value = ''

  // 立即發佈：在送出當下計算時間，避免元件掛載時算好的時間已經過期
  const isNow = schedulePicker.value?.mode === 'now'
  const resolvedScheduledAt = isNow
    ? new Date(Date.now() + 15000).toISOString()
    : scheduledAt.value

  if (!pendingImageFile.value) {
    submitError.value = '請選擇圖片'
    return
  }

  const fd = new FormData()
  fd.append('file', pendingImageFile.value)
  fd.append('caption', caption.value)
  fd.append('platforms', JSON.stringify(selectedPlatforms.value))
  fd.append('scheduled_at', resolvedScheduledAt)
  if (accountType.value === 'fb') {
    fd.append('page_db_id', String(selectedPageId.value))
  } else {
    fd.append('ig_account_db_id', String(selectedIgId.value))
  }

  submitting.value = true
  try {
    await api.post('/posts', fd)
    showSuccess.value = true
  } catch (e) {
    submitError.value = e.response?.data?.detail || '送出失敗，請重試'
  } finally {
    submitting.value = false
  }
}

function resetForm() {
  selectedPageId.value = ''
  selectedIgId.value = ''
  selectedPlatforms.value = []
  caption.value = ''
  scheduledAt.value = null
  pendingImageFile.value = null
  photoUploadKey.value += 1
  hashtagSuggestions.value = null
  selectedHashtags.value = []
  submitError.value = ''
  showSuccess.value = false
}
</script>

<style scoped>
.publish-view { display: flex; flex-direction: column; gap: 1.5rem; }
.page-header { display: flex; align-items: center; gap: 1rem; }
.page-header h2 { font-size: 1.5rem; font-weight: 700; }
.back-link { color: #888; text-decoration: none; font-size: 0.9rem; }
.back-link:hover { color: #1877f2; }

.publish-form { background: #fff; border-radius: 16px; padding: 2rem; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }

.form-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; }
@media (max-width: 768px) { .form-layout { grid-template-columns: 1fr; } }

.col-left, .col-right { display: flex; flex-direction: column; gap: 1.5rem; }

.form-section { display: flex; flex-direction: column; gap: 0.5rem; }
.form-label { font-size: 0.88rem; font-weight: 600; color: #444; display: flex; align-items: center; justify-content: space-between; }
.char-count { font-weight: 400; color: #aaa; font-size: 0.78rem; }

.account-tabs { display: flex; gap: 0; border: 1.5px solid #e0e0e0; border-radius: 10px; overflow: hidden; margin-bottom: 0.5rem; }
.acct-tab {
  flex: 1; padding: 8px; border: none; background: #fff; cursor: pointer;
  font-size: 0.88rem; color: #666; transition: all 0.15s;
}
.acct-tab:first-child { border-right: 1.5px solid #e0e0e0; }
.acct-tab.active { background: #f0f7ff; color: #1877f2; font-weight: 600; }

.form-select {
  border: 1.5px solid #e0e0e0; border-radius: 10px;
  padding: 10px 14px; font-size: 0.9rem; outline: none;
  transition: border-color 0.15s; background: #fff;
}
.form-select:focus { border-color: #1877f2; }

.form-textarea {
  border: 1.5px solid #e0e0e0; border-radius: 10px;
  padding: 12px 14px; font-size: 0.9rem; resize: vertical;
  outline: none; font-family: inherit; transition: border-color 0.15s;
}
.form-textarea:focus { border-color: #1877f2; }

.hashtag-preview { display: flex; }
.btn-append-tags {
  background: #f0f7ff; border: 1px solid #1877f2; color: #1877f2;
  border-radius: 8px; padding: 6px 14px; font-size: 0.82rem; cursor: pointer;
  transition: background 0.15s;
}
.btn-append-tags:hover { background: #ddeeff; }

.submit-error { font-size: 0.85rem; color: #e53935; padding: 8px 12px; background: #fdecea; border-radius: 8px; }

.btn-submit {
  background: #1877f2; color: #fff; border: none; border-radius: 12px;
  padding: 14px 24px; font-size: 1rem; font-weight: 600; cursor: pointer;
  display: flex; align-items: center; justify-content: center; gap: 8px;
  transition: background 0.15s, transform 0.1s;
}
.btn-submit:hover:not(:disabled) { background: #166fe5; transform: translateY(-1px); }
.btn-submit:disabled { opacity: 0.5; cursor: not-allowed; }

.spinner {
  display: inline-block; width: 16px; height: 16px;
  border: 2px solid rgba(255,255,255,0.4); border-top-color: #fff;
  border-radius: 50%; animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 999;
}
.modal-card {
  background: #fff; border-radius: 20px; padding: 2.5rem;
  text-align: center; max-width: 380px; width: 90%;
  box-shadow: 0 16px 48px rgba(0,0,0,0.2);
}
.modal-icon { font-size: 3rem; margin-bottom: 0.75rem; }
.modal-card h3 { font-size: 1.2rem; font-weight: 700; margin-bottom: 0.5rem; }
.modal-card p { color: #666; font-size: 0.9rem; margin-bottom: 1.5rem; }
.modal-actions { display: flex; gap: 0.75rem; justify-content: center; }
.btn-primary {
  background: #1877f2; color: #fff; text-decoration: none;
  padding: 10px 20px; border-radius: 10px; font-weight: 600; font-size: 0.9rem;
}
.btn-secondary {
  background: #f0f2f5; color: #333; border: none;
  padding: 10px 20px; border-radius: 10px; font-weight: 600; font-size: 0.9rem; cursor: pointer;
}
</style>
