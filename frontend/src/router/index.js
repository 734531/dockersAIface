import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import SuperHome from '../views/SuperHome.vue'
import AdminHome from '../views/AdminHome.vue'

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', component: Login },
  { path: '/super', component: SuperHome, meta: { role: 'super_admin' }},
  { path: '/admin', component: AdminHome, meta: { role: 'admin' }}
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  if (to.path === '/login') return true
  const token = localStorage.getItem('token')
  const user = JSON.parse(localStorage.getItem('user') || 'null')
  if (!token || !user) return '/login'
  if (to.meta.role && to.meta.role !== user.role) {
    return user.role === 'super_admin' ? '/super' : '/admin'
  }
  return true
})

export default router
