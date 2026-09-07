<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { reEnhanceEndpoint, updateEndpoint } from '../api'

const props = defineProps({
  endpoint: { type: Object, default: null },
  endpointId: { type: String, default: null },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits([
  'update:loading',
  'endpoint-updated',
])

const editMode = ref(false)
const editForm = ref({ description: '', edgeCases: [] })

// 切换接口时退出编辑模式
watch(() => props.endpointId, () => {
  editMode.value = false
})

function methodTagType(method) {
  const map = { GET: 'success', POST: 'warning', PUT: 'primary', DELETE: 'danger', PATCH: 'info' }
  return map[method] || 'info'
}

async function handleReEnhance() {
  if (!props.endpointId) return
  emit('update:loading', true)
  try {
    const data = await reEnhanceEndpoint(props.endpointId)
    emit('endpoint-updated', props.endpointId, data)
    ElMessage.success('AI 增强已重新生成')
  } catch (err) {
    ElMessage.error('增强失败：' + (err.response?.data?.detail || err.message))
  } finally {
    emit('update:loading', false)
  }
}

function startEdit() {
  editForm.value = {
    description: props.endpoint?.description || '',
    edgeCases: [...(props.endpoint?.edgeCases || [])],
  }
  editMode.value = true
}

async function saveEdit() {
  try {
    await updateEndpoint(props.endpointId, {
      description: editForm.value.description,
      edgeCases: editForm.value.edgeCases,
    })
    // 更新本地数据
    const updated = { ...props.endpoint }
    updated.description = editForm.value.description
    updated.edgeCases = editForm.value.edgeCases
    emit('endpoint-updated', props.endpointId, updated)
    editMode.value = false
    ElMessage.success('保存成功')
  } catch (err) {
    ElMessage.error('保存失败：' + (err.response?.data?.detail || err.message))
  }
}

function cancelEdit() {
  editMode.value = false
}

function formatJSON(str) {
  if (!str) return ''
  try {
    return JSON.stringify(JSON.parse(str), null, 2)
  } catch {
    return str
  }
}
</script>

<template>
  <div v-if="!endpoint" class="empty-tip">
    <el-empty description="请从左侧选择一个接口查看详情" />
  </div>
  <div v-else class="endpoint-detail">
    <!-- 接口基本信息 -->
    <el-card class="detail-card" shadow="never">
      <template #header>
        <div class="card-header">
          <div>
            <el-tag :type="methodTagType(endpoint.method)" size="large">
              {{ endpoint.method }}
            </el-tag>
            <span class="ep-full-path">{{ endpoint.fullPath }}</span>
          </div>
          <div>
            <el-button size="small" @click="handleReEnhance" :loading="loading">
              <el-icon><Refresh /></el-icon>
              重新增强
            </el-button>
            <el-button v-if="!editMode" size="small" type="primary" @click="startEdit">
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
            <el-button v-else size="small" type="success" @click="saveEdit">保存</el-button>
            <el-button v-if="editMode" size="small" @click="cancelEdit">取消</el-button>
          </div>
        </div>
      </template>

      <!-- 接口描述 -->
      <div class="detail-section">
        <span class="section-label">接口描述</span>
        <el-input
          v-if="editMode"
          v-model="editForm.description"
          type="textarea"
          :rows="2"
        />
        <p v-else class="section-content">{{ endpoint.description || '（未生成描述）' }}</p>
      </div>

      <!-- 方法名和返回类型 -->
      <div class="detail-meta">
        <span>方法名: <code>{{ endpoint.javaMethod }}</code></span>
        <span v-if="endpoint.returnType">返回类型: <code>{{ endpoint.returnType }}</code></span>
      </div>
    </el-card>

    <!-- 请求参数 -->
    <el-card v-if="endpoint.params?.length" class="detail-card" shadow="never">
      <template #header><span class="card-title">请求参数</span></template>
      <el-table :data="endpoint.params" border stripe>
        <el-table-column prop="name" label="参数名" width="150" />
        <el-table-column prop="type" label="类型" width="120" />
        <el-table-column label="位置" width="100">
          <template #default="{ row }">
            {{ row.annotation || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="必填" width="80">
          <template #default="{ row }">
            <el-tag :type="row.required ? 'danger' : 'info'" size="small">
              {{ row.required ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="说明" />
        <el-table-column prop="example" label="示例" width="200" />
      </el-table>
    </el-card>

    <!-- 请求示例 -->
    <el-card v-if="endpoint.requestExample" class="detail-card" shadow="never">
      <template #header><span class="card-title">请求示例</span></template>
      <pre class="json-block">{{ formatJSON(endpoint.requestExample) }}</pre>
    </el-card>

    <!-- 响应示例 -->
    <el-card v-if="endpoint.responseExample" class="detail-card" shadow="never">
      <template #header><span class="card-title">响应示例</span></template>
      <pre class="json-block">{{ formatJSON(endpoint.responseExample) }}</pre>
    </el-card>

    <!-- 边界场景 -->
    <el-card v-if="endpoint.edgeCases?.length || editMode" class="detail-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span class="card-title">边界场景</span>
          <el-button v-if="editMode" size="small" @click="editForm.edgeCases.push('')">
            <el-icon><Plus /></el-icon>
            添加
          </el-button>
        </div>
      </template>
      <div v-if="!editMode">
        <ul class="edge-list">
          <li v-for="(item, i) in endpoint.edgeCases" :key="i">{{ item }}</li>
        </ul>
      </div>
      <div v-else>
        <el-input
          v-for="(item, i) in editForm.edgeCases"
          :key="i"
          v-model="editForm.edgeCases[i]"
          class="edge-input"
        >
          <template #append>
            <el-button @click="editForm.edgeCases.splice(i, 1)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </template>
        </el-input>
      </div>
    </el-card>

    <!-- 错误码 -->
    <el-card v-if="endpoint.errorCodes?.length" class="detail-card" shadow="never">
      <template #header><span class="card-title">错误码</span></template>
      <el-table :data="endpoint.errorCodes" border stripe>
        <el-table-column prop="code" label="状态码" width="120" />
        <el-table-column prop="description" label="说明" />
      </el-table>
    </el-card>

    <!-- 源码 -->
    <el-card v-if="endpoint.sourceCode" class="detail-card" shadow="never">
      <template #header><span class="card-title">源码片段</span></template>
      <pre class="source-block">{{ endpoint.sourceCode }}</pre>
    </el-card>
  </div>
</template>

<style scoped>
.empty-tip {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.endpoint-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-card {
  margin-bottom: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-weight: 600;
}

.detail-section {
  margin-bottom: 12px;
}

.section-label {
  font-weight: 600;
  color: #909399;
  font-size: 13px;
  display: block;
  margin-bottom: 4px;
}

.section-content {
  margin: 0;
  font-size: 14px;
  color: #303133;
  line-height: 1.6;
}

.detail-meta {
  display: flex;
  gap: 24px;
  font-size: 13px;
  color: #909399;
}

.detail-meta code {
  color: #409eff;
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 4px;
}

.json-block,
.source-block {
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 12px 16px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.6;
  overflow-x: auto;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}

.source-block {
  max-height: 400px;
  overflow-y: auto;
}

.edge-list {
  margin: 0;
  padding-left: 20px;
}

.edge-list li {
  line-height: 2;
  font-size: 14px;
}

.edge-input {
  margin-bottom: 8px;
}

.ep-full-path {
  font-weight: 600;
  font-size: 15px;
  margin-left: 8px;
}
</style>
