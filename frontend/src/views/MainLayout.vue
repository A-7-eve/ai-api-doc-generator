<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { logout } from '../api'

const route = useRoute()
const router = useRouter()

// 导出中心是动态路由（/export/:id），高亮“项目历史”入口
const activeNav = computed(() => (route.path.startsWith('/export/') ? '/projects' : route.path))

const currentUser = computed(() => {
  try {
    return JSON.parse(localStorage.getItem('user') || 'null')
  } catch {
    return null
  }
})
const isAdmin = computed(() => currentUser.value?.role === 'admin')

function handleLogout() {
  logout()
  router.push('/login')
}
</script>

<template>
  <el-container class="layout-container">
    <!-- 侧边导航 -->
    <el-aside width="200px" class="layout-aside">
      <div class="logo">
        <el-icon size="22" color="#409eff"><Document /></el-icon>
        <span>AI 接口文档</span>
      </div>
      <el-menu :default-active="activeNav" router class="aside-menu">
        <el-menu-item index="/workspace">
          <el-icon><MagicStick /></el-icon>
          <span>解析工作台</span>
        </el-menu-item>
        <el-menu-item index="/projects">
          <el-icon><FolderOpened /></el-icon>
          <span>项目历史</span>
        </el-menu-item>
        <el-menu-item v-if="isAdmin" index="/users">
          <el-icon><UserFilled /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <!-- 顶栏 -->
      <el-header class="layout-header">
        <div class="page-title">{{ route.meta.title || '解析工作台' }}</div>
        <div class="header-right">
          <span v-if="currentUser" class="user-chip">
            <el-icon><User /></el-icon>
            {{ currentUser.username }}
            <el-tag :type="isAdmin ? 'danger' : 'info'" size="small">
              {{ isAdmin ? '管理员' : '普通用户' }}
            </el-tag>
          </span>
          <el-button text @click="handleLogout">
            <el-icon><SwitchButton /></el-icon>
            退出
          </el-button>
        </div>
      </el-header>

      <!-- 页面内容 -->
      <el-main class="layout-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout-container {
  height: 100vh;
}

.layout-aside {
  background: #fff;
  border-right: 1px solid #e4e7ed;
}

.logo {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 60px;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  border-bottom: 1px solid #e4e7ed;
}

.aside-menu {
  border-right: none;
}

.layout-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  height: 60px;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #606266;
}

.layout-main {
  background: #f5f7fa;
  padding: 16px;
  overflow: auto;
}
</style>
