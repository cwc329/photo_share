<template>
  <div class="app-wrapper">
    <nav v-if="auth.isLoggedIn" class="navbar">
      <div class="navbar-brand">
        <span class="brand-icon">📸</span>
        <span class="brand-name">PhotoShare</span>
      </div>
      <div class="navbar-links">
        <RouterLink to="/dashboard">Dashboard</RouterLink>
        <RouterLink to="/publish">發佈</RouterLink>
        <button class="btn-logout" @click="handleLogout">登出</button>
      </div>
    </nav>
    <main class="main-content">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const auth = useAuthStore()
const router = useRouter()

async function handleLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f0f2f5;
  color: #1a1a2e;
  min-height: 100vh;
}

.app-wrapper { min-height: 100vh; display: flex; flex-direction: column; }

.navbar {
  background: #fff;
  border-bottom: 1px solid #e0e0e0;
  padding: 0 2rem;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.navbar-brand { display: flex; align-items: center; gap: 8px; }
.brand-icon { font-size: 1.4rem; }
.brand-name { font-size: 1.1rem; font-weight: 700; color: #1877f2; }

.navbar-links { display: flex; align-items: center; gap: 1rem; }
.navbar-links a {
  color: #555;
  text-decoration: none;
  font-weight: 500;
  padding: 6px 12px;
  border-radius: 8px;
  transition: background 0.15s;
}
.navbar-links a:hover, .navbar-links a.router-link-active { background: #f0f2f5; color: #1877f2; }

.btn-logout {
  background: none;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 6px 14px;
  cursor: pointer;
  font-size: 0.9rem;
  color: #555;
  transition: all 0.15s;
}
.btn-logout:hover { border-color: #f00; color: #f00; }

.main-content { flex: 1; padding: 2rem; max-width: 1100px; margin: 0 auto; width: 100%; }
</style>
