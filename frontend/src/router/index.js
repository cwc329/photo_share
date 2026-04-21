import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import LoginView from '@/views/LoginView.vue'
import DashboardView from '@/views/DashboardView.vue'
import PublishView from '@/views/PublishView.vue'
import OAuthCallbackView from '@/views/OAuthCallbackView.vue'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/login', component: LoginView, meta: { public: true } },
  {
    path: '/oauth/callback',
    component: OAuthCallbackView,
    props: { provider: 'fb' },
    meta: { public: true },
  },
  {
    path: '/oauth/ig/callback',
    component: OAuthCallbackView,
    props: { provider: 'ig' },
    meta: { public: true },
  },
  { path: '/dashboard', component: DashboardView },
  { path: '/publish', component: PublishView },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.isLoggedIn && !auth.loading) {
    await auth.fetchMe()
  }
  if (!to.meta.public && !auth.isLoggedIn) {
    localStorage.setItem('loginRedirect', to.fullPath)
    return '/login'
  }
  if (to.path === '/login' && auth.isLoggedIn) {
    return '/dashboard'
  }
})

export default router
