<template>
  <div class="hashtag-picker" v-if="hasSuggestions">
    <p class="picker-title">EXIF Hashtag 建議 <span class="hint">點擊加入文案</span></p>
    <div v-for="(tags, category) in filteredSuggestions" :key="category" class="category-group">
      <span class="category-label">{{ categoryLabel(category) }}</span>
      <div class="tags-row">
        <button
          v-for="tag in tags"
          :key="tag"
          type="button"
          class="tag-btn"
          :class="{ selected: selected.has(tag) }"
          @click="toggle(tag)"
        >
          {{ tag }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive } from 'vue'

const props = defineProps({
  suggestions: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['update:selected-tags'])

const selected = reactive(new Set())

const LABELS = {
  camera: '相機',
  lens: '鏡頭',
  focal_length: '焦距',
  focal_length_35mm: '等效焦距',
  iso: 'ISO',
  aperture: '光圈',
  shutter: '快門',
  software: '修圖軟體',
  location: '地點',
}

const filteredSuggestions = computed(() =>
  Object.fromEntries(
    Object.entries(props.suggestions).filter(([, tags]) => tags && tags.length > 0)
  )
)

const hasSuggestions = computed(() => Object.keys(filteredSuggestions.value).length > 0)

function categoryLabel(key) { return LABELS[key] || key }

function toggle(tag) {
  if (selected.has(tag)) {
    selected.delete(tag)
  } else {
    selected.add(tag)
  }
  emit('update:selected-tags', [...selected])
}
</script>

<style scoped>
.hashtag-picker { background: #f8f9ff; border-radius: 12px; padding: 1rem; }
.picker-title { font-size: 0.88rem; font-weight: 600; color: #444; margin-bottom: 0.75rem; }
.hint { font-weight: 400; color: #aaa; font-size: 0.78rem; margin-left: 6px; }

.category-group { margin-bottom: 0.75rem; }
.category-label { font-size: 0.75rem; color: #888; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
.tags-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }

.tag-btn {
  background: #fff; border: 1px solid #ddd; border-radius: 20px;
  padding: 4px 12px; font-size: 0.82rem; cursor: pointer; color: #555;
  transition: all 0.15s;
}
.tag-btn:hover { border-color: #1877f2; color: #1877f2; }
.tag-btn.selected { background: #1877f2; border-color: #1877f2; color: #fff; }
</style>
