<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import ApiTree from '../components/ApiTree.vue'
import EndpointDetail from '../components/EndpointDetail.vue'
import { parseProjectFile, parseProjectPath, parseSample } from '../api'

const router = useRouter()

const project = ref(null)
const loading = ref(false)
const activeEndpointId = ref(null)
const activeEndpoint = ref(null)
const pathInput = ref('')

function selectEndpoint(endpointId, endpointData) {
  activeEndpointId.value = endpointId
  activeEndpoint.value = endpointData
}

function handleEndpointUpdated(endpointId, data) {
  activeEndpoint.value = data
  if (!project.value) return
  for (const ctrl of project.value.controllers) {
    for (const ep of ctrl.endpoints) {
      if (ep.endpointId === endpointId) {
        Object.assign(ep, data)
        return
      }
    }
  }
}

function onParsed(data) {
  project.value = data
  activeEndpointId.value = null
  activeEndpoint.value = null
}

async function handleUpload(file) {
  loading.value = true
  try {
    const data = await parseProjectFile(file)
    onParsed(data)
    ElMessage.success(`解析成功：${data.controllers.length} 个 Controller，${countEndpoints(data)} 个接口`)
  } catch (err) {
    ElMessage.error('解析失败：' + (err.response?.data?.detail || err.message))
  } finally {
    loading.value = false
  }
}

async function handleParsePath() {
  if (!pathInput.value.trim()) {
    ElMessage.warning('请输入项目路径')
    return
  }
  loading.value = true
  try {
    const data = await parseProjectPath(pathInput.value.trim())
    onParsed(data)
    ElMessage.success(`解析成功：${data.controllers.length} 个 Controller，${countEndpoints(data)} 个接口`)
  } catch (err) {
    ElMessage.error('解析失败：' + (err.response?.data?.detail || err.message))
  } finally {
    loading.value = false
  }
}

async function handleParseSample() {
  loading.value = true
  try {
    const data = await parseSample()
    onParsed(data)
    ElMessage.success(`解析成功：${data.controllers.length} 个 Controller，${countEndpoints(data)} 个接口`)
  } catch (err) {
    ElMessage.error('解析失败：' + (err.response?.data?.detail || err.message))
  } finally {
    loading.value = false
  }
}

function countEndpoints(data) {
  return data.controllers.reduce((s, c) => s + c.endpoints.length, 0)
}

// 去导出中心：携带当前项目 ID
function goExport() {
  if (!project.value?.projectId) {
    ElMessage.warning('请先解析项目')
    return
  }
  router.push(`/export/${project.value.projectId}`)
}
</script>

<template>
  <div class="workspace">
    <!-- 工具栏：解析入口 -->
    <el-card shadow="never" class="toolbar-card">
      <div class="toolbar">
        <el-button type="primary" plain @click="handleParseSample" :loading="loading">
          <el-icon><MagicStick /></el-icon>
          解析内置示例
        </el-button>
        <el-upload
          :auto-upload="true"
          :show-file-list="false"
          :http-request="(opt) => handleUpload(opt.file)"
          accept=".zip"
        >
          <el-button type="primary" :loading="loading">
            <el-icon><Upload /></el-icon>
            上传ZIP项目
          </el-button>
        </el-upload>
        <el-input
          v-model="pathInput"
          placeholder="输入本地项目路径"
          style="width: 300px"
          @keyup.enter="handleParsePath"
        />
        <el-button @click="handleParsePath" :loading="loading">
          <el-icon><FolderOpened /></el-icon>
          解析路径
        </el-button>
        <div class="spacer" />
        <el-button-group v-if="project">
          <el-button type="success" @click="goExport">
            <el-icon><Download /></el-icon>
            前往导出中心
          </el-button>
        </el-button-group>
      </div>
    </el-card>

    <!-- 主体：接口树 + 详情 -->
    <el-row :gutter="16" class="main-row" v-loading="loading" element-loading-text="正在解析和 AI 增强...">
      <el-col :span="6" class="left-panel">
        <ApiTree
          :project="project"
          :active-endpoint-id="activeEndpointId"
          @select-endpoint="selectEndpoint"
        />
      </el-col>
      <el-col :span="18" class="right-panel">
        <EndpointDetail
          :endpoint="activeEndpoint"
          :endpoint-id="activeEndpointId"
          :loading="loading"
          @update:loading="loading = $event"
          @endpoint-updated="handleEndpointUpdated"
        />
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.workspace {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.toolbar-card :deep(.el-card__body) {
  padding: 12px 16px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.spacer {
  flex: 1;
}

.main-row {
  flex: 1;
  height: calc(100% - 62px);
  overflow: hidden;
}

.left-panel {
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  padding: 12px;
  height: 100%;
  overflow: hidden;
}

.right-panel {
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  padding: 16px;
  height: 100%;
  overflow-y: auto;
}
</style>
