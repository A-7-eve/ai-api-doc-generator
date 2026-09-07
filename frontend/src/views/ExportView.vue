<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getProject, exportProject, getFilenameFromDisposition } from '../api'

const route = useRoute()
const projectId = route.params.projectId

const project = ref(null)
const loading = ref(false)
const previewTab = ref('markdown')
const previewContent = ref('')
const previewLoading = ref(false)

const endpointCount = computed(() =>
  (project.value?.controllers || []).reduce((s, c) => s + (c.endpoints || []).length, 0)
)

async function load() {
  loading.value = true
  try {
    project.value = await getProject(projectId)
    await loadPreview('markdown')
  } catch (err) {
    ElMessage.error('获取项目失败：' + (err.response?.data?.detail || err.message))
  } finally {
    loading.value = false
  }
}

// 预览：拉取 Markdown 文本直接展示；OpenAPI 以 JSON 文本展示
async function loadPreview(format) {
  previewLoading.value = true
  try {
    const res = await exportProject(projectId, format)
    const text = await res.data.text()
    if (format === 'openapi') {
      // 格式化 JSON 便于阅读
      try {
        previewContent.value = JSON.stringify(JSON.parse(text), null, 2)
      } catch {
        previewContent.value = text
      }
    } else {
      previewContent.value = text
    }
  } catch (err) {
    ElMessage.error('加载预览失败：' + (err.response?.data?.detail || err.message))
  } finally {
    previewLoading.value = false
  }
}

function handleTabChange(name) {
  // el-tabs 的 tab-change 事件参数即标签名（字符串）
  loadPreview(name)
}

async function handleDownload(format) {
  try {
    const res = await exportProject(projectId, format)
    const ext = format === 'openapi' ? 'json' : 'md'
    const fallback = `${project.value?.projectName || 'project'}_api_doc.${ext}`
    const filename = getFilenameFromDisposition(res.headers['content-disposition'], fallback)
    const blob = new Blob([res.data])
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    // 必须先挂到 DOM 再点击，否则部分浏览器忽略 download 属性
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success(`已导出 ${filename}`)
  } catch (err) {
    ElMessage.error('导出失败：' + (err.response?.data?.detail || err.message))
  }
}

onMounted(load)
</script>

<template>
  <div class="export-view">
    <!-- 项目信息卡片 -->
    <el-card shadow="never" v-loading="loading">
      <div class="project-info">
        <div class="info-main">
          <span class="project-name">{{ project?.projectName || '加载中...' }}</span>
          <el-tag type="success" size="small">{{ (project?.controllers || []).length }} 个 Controller</el-tag>
          <el-tag type="info" size="small">{{ endpointCount }} 个接口</el-tag>
          <el-tag v-if="project?.ownerName" size="small">归属：{{ project.ownerName }}</el-tag>
        </div>
        <el-button-group>
          <el-button type="primary" @click="handleDownload('markdown')">
            <el-icon><Download /></el-icon>
            下载 Markdown
          </el-button>
          <el-button type="success" @click="handleDownload('openapi')">
            <el-icon><Download /></el-icon>
            下载 OpenAPI JSON
          </el-button>
        </el-button-group>
      </div>
    </el-card>

    <!-- 文档预览 -->
    <el-card shadow="never" class="preview-card" v-loading="previewLoading">
      <template #header>
        <el-tabs v-model="previewTab" @tab-change="handleTabChange">
          <el-tab-pane label="Markdown 预览" name="markdown" />
          <el-tab-pane label="OpenAPI 源码" name="openapi" />
        </el-tabs>
      </template>
      <pre class="preview-content">{{ previewContent }}</pre>
    </el-card>
  </div>
</template>

<style scoped>
.export-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
}

.project-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}

.info-main {
  display: flex;
  align-items: center;
  gap: 10px;
}

.project-name {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.preview-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.preview-card :deep(.el-card__body) {
  flex: 1;
  overflow: auto;
  padding: 0;
}

.preview-content {
  margin: 0;
  padding: 16px;
  font-family: 'Cascadia Code', Consolas, monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
