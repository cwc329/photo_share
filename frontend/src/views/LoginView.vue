<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-logo">📸</div>
      <h1 class="login-title">PhotoShare</h1>
      <p class="login-subtitle">將你的照片一鍵發佈至 Facebook & Instagram</p>

      <ul class="feature-list">
        <li>📷 自動讀取 EXIF 資訊產生 Hashtag 建議</li>
        <li>📅 排程發佈，自動在指定時間發文</li>
        <li>🔁 同時發佈至多個平台</li>
      </ul>

      <div class="login-divider-label">選擇登入方式</div>

      <!-- Facebook Login for Business -->
      <a class="btn-login btn-fb" :href="fbLoginUrl">
        <svg viewBox="0 0 24 24" fill="white" width="20" height="20">
          <path d="M24 12.073C24 5.405 18.627 0 12 0S0 5.405 0 12.073C0 18.1 4.388 23.094 10.125 24v-8.437H7.078v-3.49h3.047V9.41c0-3.025 1.792-4.697 4.533-4.697 1.312 0 2.686.236 2.686.236v2.97h-1.514c-1.491 0-1.956.93-1.956 1.874v2.25h3.328l-.532 3.49h-2.796V24C19.612 23.094 24 18.1 24 12.073z"/>
        </svg>
        以 Facebook 帳號登入
      </a>
      <p class="login-note">需有 Facebook 粉絲專頁，可同時發佈 FB 與連結的 IG</p>

      <div class="login-or"><span>或</span></div>

      <!-- Instagram Business Login -->
      <a class="btn-login btn-ig" :href="igLoginUrl">
        <svg viewBox="0 0 24 24" fill="white" width="20" height="20">
          <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
        </svg>
        以 Instagram 帳號登入
      </a>
      <p class="login-note">只需 Instagram 專業帳號（商業或創作者），不需 Facebook 粉專</p>
    </div>
  </div>
</template>

<script setup>
const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'
const fbLoginUrl = `${apiBase}/auth/login`
const igLoginUrl = `${apiBase}/auth/ig/login`
</script>

<style scoped>
.login-page {
  min-height: calc(100vh - 60px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
}

.login-card {
  background: #fff;
  border-radius: 20px;
  padding: 3rem 2.5rem;
  max-width: 440px;
  width: 100%;
  text-align: center;
  box-shadow: 0 8px 32px rgba(0,0,0,0.1);
}

.login-logo { font-size: 3.5rem; margin-bottom: 0.5rem; }
.login-title { font-size: 1.8rem; font-weight: 800; color: #1a1a2e; margin-bottom: 0.5rem; }
.login-subtitle { color: #666; font-size: 0.95rem; margin-bottom: 1.8rem; }

.feature-list {
  list-style: none;
  text-align: left;
  background: #f8f9ff;
  border-radius: 12px;
  padding: 1rem 1.2rem;
  margin-bottom: 1.5rem;
}
.feature-list li { padding: 0.35rem 0; font-size: 0.9rem; color: #444; }

.login-divider-label {
  font-size: 0.78rem;
  color: #aaa;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 1rem;
}

.btn-login {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border: none;
  border-radius: 12px;
  padding: 14px 24px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
  transition: filter 0.2s, transform 0.1s;
  width: 100%;
  color: #fff;
}
.btn-login:hover { filter: brightness(1.1); transform: translateY(-1px); }
.btn-login:active { transform: translateY(0); }

.btn-fb { background: #1877f2; }
.btn-ig { background: linear-gradient(135deg, #f58529, #dd2a7b, #8134af); }

.login-or {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin: 1rem 0;
  color: #ccc;
  font-size: 0.85rem;
}
.login-or::before, .login-or::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #eee;
}

.login-note { font-size: 0.78rem; color: #999; margin-top: 0.5rem; margin-bottom: 1rem; }
</style>
