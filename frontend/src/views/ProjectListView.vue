<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listProjects, deleteProject } from '../api'

const router = useRouter()

const projects = ref([])
const loading = ref(false)
const keyword = ref('')

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return projects.value
  return projects.value.filter(
    (p) =>
      (p.projectName || '').toLowerCase().includes(kw) ||
      (p.ownerName || '').toLowerCase().includes(kw)
  )
})

async function load() {
  loading.value = true
  try {
    projects.value = await listProjects()
  } catch (err) {
    ElMessage.error('获取项目列表失败：' + (err.response?.data?.detail || err.message))
  } finally {
    loading.value = false
  }
}

function countEndpoints(p) {
  return (p.controllers || []).reduce((s, c) => s + (c.endpoints || []).length, 0)
}

function goExport(p) {
  router.push(`/export/${p.projectId}`)
}

function handleDelete(p) {
  ElMessageBox.confirm(
    `确定删除项目「${p.projectName}」？其下所有接口数据将一并删除，无法恢复。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
  )
    .then(async () => {
      try {
        await deleteProject(p.projectId)
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
  <div class="project-list">
    <el-card shadow="never">
      <div class="list-toolbar">
        <el-input
          v-model="keyword"
          placeholder="按项目名 / 归属人搜索"
          style="width: 260px"
          clearable
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <span class="count-hint">共 {{ filtered.length }} 个项目</span>
        <div class="spacer" />
        <el-button @click="load" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>

      <el-table :data="filtered" v-loading="loading" style="width: 100%">
        <el-table-column prop="projectName" label="项目名称" min-width="200" show-overflow-tooltip />
        <el-table-column label="Controller 数" width="130">
          <template #default="{ row }">{{ (row.controllers || []).length }}</template>
        </el-table-column>
        <el-table-column label="接口数" width="100">
          <template #default="{ row }">{{ countEndpoints(row) }}</template>
        </el-table-column>
        <el-table-column prop="ownerName" label="归属人" width="120">
          <template #default="{ row }">{{ row.ownerName || '—（历史数据）' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click="goExport(row)">
              查看与导出
            </el-button>
            <el-button size="small" type="danger" plain @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && filtered.length === 0" description="暂无项目，去工作台解析一个吧" />
    </el-card>
  </div>
</template>

<style scoped>
.list-toolbar {
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
