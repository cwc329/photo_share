<template>
  <div class="platform-selector">
    <!-- Facebook option: only show when using FB Page login -->
    <label v-if="accountType === 'fb'" class="platform-option" :class="{ disabled: !hasFacebook }">
      <input
        type="checkbox"
        :disabled="!hasFacebook"
        :checked="modelValue.includes('facebook')"
        @change="toggle('facebook', $event)"
      />
      <span class="platform-icon">📘</span>
      <span class="platform-name">Facebook</span>
      <span v-if="!hasFacebook" class="platform-note">（需選擇 Page）</span>
    </label>

    <!-- Instagram option -->
    <label class="platform-option" :class="{ disabled: !hasInstagram }">
      <input
        type="checkbox"
        :disabled="!hasInstagram"
        :checked="modelValue.includes('instagram')"
        @change="toggle('instagram', $event)"
      />
      <span class="platform-icon">📷</span>
      <span class="platform-name">Instagram</span>
      <span v-if="accountType === 'fb' && selectedPage && !hasInstagram" class="platform-note">
        （此 Page 未連結 IG）
      </span>
    </label>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  accountType: { type: String, default: 'fb' },  // 'fb' | 'ig'
  selectedPage: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue'])

const hasFacebook = computed(() => props.accountType === 'fb' && !!props.selectedPage)
const hasInstagram = computed(() => {
  if (props.accountType === 'ig') return true
  return !!props.selectedPage?.ig_account_id
})

function toggle(platform, e) {
  const checked = e.target.checked
  const current = [...props.modelValue]
  if (checked && !current.includes(platform)) {
    emit('update:modelValue', [...current, platform])
  } else if (!checked) {
    emit('update:modelValue', current.filter((p) => p !== platform))
  }
}
</script>

<style scoped>
.platform-selector { display: flex; gap: 1rem; flex-wrap: wrap; }
.platform-option {
  display: flex; align-items: center; gap: 6px;
  cursor: pointer; padding: 10px 16px; border: 1.5px solid #eee;
  border-radius: 12px; user-select: none; transition: border-color 0.15s;
}
.platform-option:not(.disabled):hover { border-color: #1877f2; }
.platform-option.disabled { opacity: 0.5; cursor: not-allowed; }
.platform-option input { width: 16px; height: 16px; cursor: pointer; }
.platform-icon { font-size: 1.1rem; }
.platform-name { font-weight: 600; font-size: 0.9rem; }
.platform-note { font-size: 0.78rem; color: #aaa; }
</style>
