<template>
  <div class="photo-upload">
    <div
      class="drop-zone"
      :class="{ 'drag-over': isDragging, 'has-image': previewUrl }"
      @dragover.prevent="isDragging = true"
      @dragleave="isDragging = false"
      @drop.prevent="onDrop"
      @click="fileInput.click()"
    >
      <img v-if="previewUrl" :src="previewUrl" class="preview-img" />
      <div v-else class="drop-placeholder">
        <span class="upload-icon">📁</span>
        <p>點擊或拖曳圖片上傳</p>
        <p class="upload-hint">支援 JPG、PNG、WebP，最大 20MB</p>
      </div>
      <div v-if="previewUrl" class="change-overlay">
        <span>更換圖片</span>
      </div>
    </div>
    <input ref="fileInput" type="file" accept="image/*" hidden @change="onFileChange" />

    <div v-if="uploading" class="upload-status">
      <span class="spinner"></span> 上傳中，讀取 EXIF 資訊...
    </div>
    <div v-if="error" class="upload-error">{{ error }}</div>

    <div v-if="imageInfo" class="image-meta">
      <span>{{ imageInfo.width }} × {{ imageInfo.height }}</span>
      <span>{{ (imageInfo.size_bytes / 1024 / 1024).toFixed(2) }} MB</span>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import api from '@/api'

const emit = defineEmits(['uploaded'])

const fileInput = ref(null)
const previewUrl = ref('')
const uploading = ref(false)
const error = ref('')
const isDragging = ref(false)
const imageInfo = ref(null)

async function uploadFile(file) {
  if (!file) return
  error.value = ''
  uploading.value = true
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = URL.createObjectURL(file)

  try {
    const form = new FormData()
    form.append('file', file)
    const { data } = await api.post('/media/analyze', form)
    imageInfo.value = { width: data.width, height: data.height, size_bytes: data.size_bytes }
    emit('uploaded', { file, ...data })
  } catch (e) {
    error.value = e.response?.data?.detail || '上傳失敗，請重試'
    previewUrl.value = ''
  } finally {
    uploading.value = false
  }
}

function onFileChange(e) {
  const file = e.target.files[0]
  if (file) uploadFile(file)
}

function onDrop(e) {
  isDragging.value = false
  const file = e.dataTransfer.files[0]
  if (file) uploadFile(file)
}
</script>

<style scoped>
.photo-upload { display: flex; flex-direction: column; gap: 0.75rem; }

.drop-zone {
  border: 2px dashed #d0d0d0;
  border-radius: 16px;
  cursor: pointer;
  overflow: hidden;
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  transition: border-color 0.2s, background 0.2s;
  background: #fafafa;
}
.drop-zone:hover, .drop-zone.drag-over { border-color: #1877f2; background: #f0f7ff; }
.drop-zone.has-image { border-style: solid; }

.drop-placeholder { text-align: center; color: #aaa; }
.upload-icon { font-size: 2.5rem; display: block; margin-bottom: 0.5rem; }
.drop-placeholder p { font-size: 0.9rem; }
.upload-hint { font-size: 0.78rem; margin-top: 4px; }

.preview-img { width: 100%; height: 100%; object-fit: contain; max-height: 320px; }

.change-overlay {
  position: absolute; inset: 0;
  background: rgba(0,0,0,0.45);
  color: #fff; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
  opacity: 0; transition: opacity 0.2s;
}
.drop-zone:hover .change-overlay { opacity: 1; }

.upload-status { display: flex; align-items: center; gap: 8px; font-size: 0.88rem; color: #555; }
.spinner {
  display: inline-block; width: 16px; height: 16px;
  border: 2px solid #ddd; border-top-color: #1877f2;
  border-radius: 50%; animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.upload-error { font-size: 0.85rem; color: #e53935; }
.image-meta { display: flex; gap: 1rem; font-size: 0.8rem; color: #888; }
</style>
