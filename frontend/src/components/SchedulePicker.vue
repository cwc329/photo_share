<template>
  <div class="schedule-picker">
    <div class="mode-tabs">
      <button
        type="button"
        class="mode-tab"
        :class="{ active: mode === 'now' }"
        @click="setMode('now')"
      >立即發佈</button>
      <button
        type="button"
        class="mode-tab"
        :class="{ active: mode === 'scheduled' }"
        @click="setMode('scheduled')"
      >排程發佈</button>
    </div>

    <div v-if="mode === 'scheduled'" class="datetime-row">
      <input
        type="datetime-local"
        class="datetime-input"
        :value="localDatetime"
        :min="minDatetime"
        @input="onDatetimeInput"
        @change="onDatetimeInput"
      />
      <p v-if="error" class="schedule-error">{{ error }}</p>
    </div>

    <div v-if="mode === 'now'" class="now-hint">
      送出後立即發佈
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const emit = defineEmits(['update:scheduledAt', 'update:mode'])

const mode = ref('now')
const localDatetime = ref('')
const error = ref('')

const MIN_MINUTES = 1

function _formatLocalDatetimeInput(d) {
  const pad = (n) => String(n).padStart(2, '0')
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  )
}

function _minAllowedDate() {
  // datetime-local 沒有秒；用「分鐘」做限制：
  // 例如現在 12:05:11，允許排到 12:06:00（而不是 12:06:11）
  const d = new Date()
  d.setSeconds(0, 0)
  d.setMinutes(d.getMinutes() + MIN_MINUTES)
  return d
}

// Minimum = MIN_MINUTES from now (recomputed on each access)
const minDatetime = computed(() => {
  return _formatLocalDatetimeInput(_minAllowedDate())
})

function setMode(m) {
  mode.value = m
  error.value = ''
  emit('update:mode', m)
  emit('update:scheduledAt', null)
  if (m === 'scheduled') {
    localDatetime.value = ''
  }
}

// 供父元件在送出時查詢目前 mode
defineExpose({ mode })

function onDatetimeInput(e) {
  const val = e.target.value
  localDatetime.value = val
  error.value = ''
  if (!val) {
    emit('update:scheduledAt', null)
    return
  }
  const selected = new Date(val)
  const minAllowed = _minAllowedDate()
  if (selected < minAllowed) {
    error.value = `排程時間至少需在 ${MIN_MINUTES} 分鐘後`
    emit('update:scheduledAt', null)
    return
  }
  // 統一送 UTC（Z）字串，避免 client 端處理 offset 格式
  emit('update:scheduledAt', selected.toISOString())
}

// Initialize with immediate mode
setMode('now')
</script>

<style scoped>
.schedule-picker { display: flex; flex-direction: column; gap: 0.75rem; }
.mode-tabs { display: flex; gap: 0; border: 1.5px solid #e0e0e0; border-radius: 10px; overflow: hidden; width: fit-content; }
.mode-tab {
  padding: 8px 18px; border: none; background: #fff; cursor: pointer;
  font-size: 0.88rem; color: #666; transition: all 0.15s;
}
.mode-tab:first-child { border-right: 1.5px solid #e0e0e0; }
.mode-tab.active { background: #1877f2; color: #fff; font-weight: 600; }

.datetime-row { display: flex; flex-direction: column; gap: 4px; }
.datetime-input {
  border: 1.5px solid #e0e0e0; border-radius: 10px;
  padding: 10px 14px; font-size: 0.9rem; outline: none;
  transition: border-color 0.15s;
}
.datetime-input:focus { border-color: #1877f2; }
.schedule-error { font-size: 0.82rem; color: #e53935; }
.now-hint { font-size: 0.85rem; color: #888; }
</style>
