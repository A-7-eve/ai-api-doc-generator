<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listUsers, updateUserRole, deleteUser } from '../api'

// 当前登录用户（从本地登录态读取）
const currentUser = computed(() => {
  try {
    return JSON.parse(localStorage.getItem('user') || 'null')
  } catch {
    return null
  }
})

const userList = ref([])
const loading = ref(false)
const keyword = ref('')

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return userList.value
  return userList.value.filter((u) => (u.username || '').toLowerCase().includes(kw))
})

async function load() {
  loading.value = true
  try {
    userList.value = await listUsers()
  } catch (err) {
    ElMessage.error('获取用户列表失败：' + (err.response?.data?.detail || err.message))
  } finally {
    loading.value = false
  }
}

async function handleRoleChange(row) {
  try {
    await updateUserRole(row.userId, row.role)
    ElMessage.success(`已将 ${row.username} 设为 ${row.role === 'admin' ? '管理员' : '普通用户'}`)
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '修改失败')
    load()
  }
}

function handleDeleteUser(row) {
  ElMessageBox.confirm(
    `确定删除用户「${row.username}」？删除后无法恢复。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
  )
    .then(async () => {
      try {
        await deleteUser(row.userId)
        ElMessage.success('已删除')
        load()
      } catch (err) {
        ElMessage.error(err.response?.data?.detail || '删除失败')
      }
    })
    .catch(() => {})
}

onMounted(load)
</script>

<template>
  <el-card shadow="never">
    <div class="user-toolbar">
      <el-input
        v-model="keyword"
        placeholder="按用户名搜索"
        style="width: 240px"
        clearable
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <span class="count-hint">共 {{ filtered.length }} 个用户</span>
      <div class="spacer" />
      <el-button @click="load" :loading="loading">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <el-table :data="filtered" v-loading="loading" style="width: 100%">
      <el-table-column prop="username" label="用户名" width="200" />
      <el-table-column label="角色" width="200">
        <template #default="{ row }">
          <el-select
            :model-value="row.role"
            :disabled="row.userId === currentUser?.userId"
            @change="handleRoleChange(row)"
          >
            <el-option label="普通用户" value="user" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column prop="createdAt" label="创建时间" min-width="180" show-overflow-tooltip />
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button
            size="small"
            type="danger"
            plain
            :disabled="row.userId === currentUser?.userId"
            @click="handleDeleteUser(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<style scoped>
.user-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.count-hint {
  font-size: 13px;
  color: #909399;
}

.spacer {
  flex: 1;
}
</style>
