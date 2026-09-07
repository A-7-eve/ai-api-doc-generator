import { createRouter, createWebHashHistory } from 'vue-router'
import { ElMessage } from 'element-plus'

// 路由懒加载：每个页面独立分包，减小首屏体积
const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('../views/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/workspace',
      },
      {
        path: 'workspace',
        name: 'workspace',
        component: () => import('../views/WorkspaceView.vue'),
        meta: { title: '解析工作台' },
      },
      {
        path: 'projects',
        name: 'projects',
        component: () => import('../views/ProjectListView.vue'),
        meta: { title: '项目历史' },
      },
      {
        path: 'export/:projectId',
        name: 'export',
        component: () => import('../views/ExportView.vue'),
        meta: { title: '导出中心' },
      },
      {
        path: 'users',
        name: 'users',
        component: () => import('../views/UserManageView.vue'),
        meta: { title: '用户管理', requiresAdmin: true },
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/workspace' },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

// 全局前置守卫：登录校验 + 角色校验
router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth !== false && !token) {
    return { name: 'login' }
  }
  // 管理员页面：普通用户拦截
  if (to.meta.requiresAdmin) {
    let user = null
    try {
      user = JSON.parse(localStorage.getItem('user') || 'null')
    } catch {
      user = null
    }
    if (!user || user.role !== 'admin') {
      ElMessage.error('该页面仅管理员可访问')
      return { name: 'workspace' }
    }
  }
  return true
})

export default router
