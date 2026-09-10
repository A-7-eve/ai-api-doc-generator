<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getProject, exportProject, getFilenameFromDisposition, getDoc, saveDoc, resetDoc } from '../api'

const route = useRoute()
const projectId = route.params.projectId

const project = ref(null)
const loading = ref(false)
const previewTab = ref('markdown')
const previewContent = ref('')
const previewLoading = ref(false)

// v2.4 在线编辑状态
const edited = ref(false)        // 当前内容是否来自编辑版
const dirty = ref(false)         // 有未保存的修改
const saving = ref(false)

const endpointCount = computed(() =>
  (project.value?.controllers || []).reduce((s, c) => s + (c.endpoints || []).length, 0)
)

// 语言标签展示（v2.4 多语言）
const languageTags = computed(() => {
  const langs = project.value?.languages || []
  return langs.length ? langs : ['java']
})

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

// 加载文档内容（v2.4：走 doc 端点，支持编辑版）
async function loadPreview(format) {
  previewLoading.value = true
  try {
    const res = await getDoc(projectId, format)
    let text = res.content
    if (format === 'openapi') {
      // 格式化 JSON 便于阅读
      try {
        text = JSON.stringify(JSON.parse(text), null, 2)
      } catch { /* 保留原文 */ }
    }
    previewContent.value = text
    edited.value = res.edited
    dirty.value = false
  } catch (err) {
    ElMessage.error('加载文档失败：' + (err.response?.data?.detail || err.message))
  } finally {
    previewLoading.value = false
  }
}

function handleTabChange(name) {
  // 切换标签前若有未保存修改，提示确认
  if (dirty.value) {
    ElMessageBox.confirm('当前有未保存的修改，切换后将丢失，是否继续？', '提示', {
      confirmButtonText: '继续',
      cancelButtonText: '取消',
      type: 'warning',
    }).then(() => {
      loadPreview(name)
    }).catch(() => {
      // 恢复标签（tab-change 时 v-model 已变，需回退）
      previewTab.value = previewTab.value === 'markdown' ? 'openapi' : 'markdown'
    })
  } else {
    loadPreview(name)
  }
}

function handleInput() {
  dirty.value = true
}

// 保存编辑版
async function handleSave() {
  saving.value = true
  try {
    const format = previewTab.value
    await saveDoc(projectId, format, previewContent.value)
    edited.value = true
    dirty.value = false
    ElMessage.success('已保存编辑版')
  } catch (err) {
    ElMessage.error('保存失败：' + (err.response?.data?.detail || err.message))
  } finally {
    saving.value = false
  }
}

// 重置为生成版
async function handleReset() {
  const format = previewTab.value
  try {
    await ElMessageBox.confirm(
      '将清除编辑版并恢复为系统生成版，该操作不可撤销，是否继续？',
      '重置确认',
      { confirmButtonText: '重置', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  previewLoading.value = true
  try {
    const res = await resetDoc(projectId, format)
    let text = res.content
    if (format === 'openapi') {
      try {
        text = JSON.stringify(JSON.parse(text), null, 2)
      } catch { /* 保留原文 */ }
    }
    previewContent.value = text
    edited.value = false
    dirty.value = false
    ElMessage.success('已恢复为生成版')
  } catch (err) {
    ElMessage.error('重置失败：' + (err.response?.data?.detail || err.message))
  } finally {
    previewLoading.value = false
  }
}

async function handleDownload(format) {
  if (dirty.value) {
    ElMessage.warning('当前有未保存的修改，下载的是已保存版本（请先保存）')
  }
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
          <el-tag v-for="lang in languageTags" :key="lang" size="small" type="warning" effect="plain">
            {{ lang }}
          </el-tag>
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

    <!-- 文档在线编辑（v2.4：预览区可编辑 + 保存/重置） -->
    <el-card shadow="never" class="preview-card" v-loading="previewLoading">
      <template #header>
        <div class="preview-header">
          <el-tabs v-model="previewTab" @tab-change="handleTabChange" class="preview-tabs">
            <el-tab-pane label="Markdown 文档" name="markdown" />
            <el-tab-pane label="OpenAPI 源码" name="openapi" />
          </el-tabs>
          <div class="edit-actions">
            <el-tag v-if="edited" type="warning" size="small" effect="light">已编辑</el-tag>
            <el-tag v-if="dirty" type="danger" size="small" effect="light">未保存</el-tag>
            <el-button size="small" type="primary" :loading="saving" :disabled="!dirty" @click="handleSave">
              <el-icon><Check /></el-icon>
              保存
            </el-button>
            <el-button size="small" :disabled="!edited && !dirty" @click="handleReset">
              <el-icon><RefreshLeft /></el-icon>
              重置
            </el-button>
          </div>
        </div>
      </template>
      <el-input
        v-model="previewContent"
        type="textarea"
        :autosize="false"
        resize="none"
        class="doc-editor"
        input-style="font-family: 'Cascadia Code', Consolas, monospace; font-size: 13px; line-height: 1.6;"
        @input="handleInput"
      />
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
  overflow: hidden;
  padding: 0;
  display: flex;
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.preview-tabs {
  flex: 1;
}

.preview-tabs :deep(.el-tabs__header) {
  margin-bottom: 0;
}

.edit-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.doc-editor {
  flex: 1;
}

.doc-editor :deep(.el-textarea__inner) {
  height: 100%;
  border: none;
  box-shadow: none;
  padding: 16px;
  border-radius: 0;
  color: #303133;
  white-space: pre;
  overflow: auto;
}
</style>
