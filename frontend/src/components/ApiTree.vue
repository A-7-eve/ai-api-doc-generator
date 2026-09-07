<script setup>
import { computed } from 'vue'

const props = defineProps({
  project: { type: Object, default: null },
  activeEndpointId: { type: String, default: null },
})

const emit = defineEmits(['select-endpoint'])

const controllerCount = computed(() => props.project?.controllers?.length || 0)
const endpointCount = computed(() => {
  if (!props.project) return 0
  return props.project.controllers.reduce((sum, c) => sum + c.endpoints.length, 0)
})

function methodTagType(method) {
  const map = { GET: 'success', POST: 'warning', PUT: 'primary', DELETE: 'danger', PATCH: 'info' }
  return map[method] || 'info'
}
</script>

<template>
  <div v-if="!project" class="empty-tip">
    <el-empty description="请上传项目或解析内置示例" />
  </div>
  <div v-else>
    <div class="project-info">
      <el-icon><Folder /></el-icon>
      <span>{{ project.projectName }}</span>
      <el-tag size="small">{{ controllerCount }} 控制器</el-tag>
      <el-tag size="small" type="success">{{ endpointCount }} 接口</el-tag>
    </div>
    <el-scrollbar height="calc(100vh - 220px)">
      <el-collapse v-for="ctrl in project.controllers" :key="ctrl.controllerId">
        <el-collapse-item :name="ctrl.controllerId">
          <template #title>
            <span class="ctrl-name">{{ ctrl.className }}</span>
            <el-badge :value="ctrl.endpoints.length" type="primary" />
          </template>
          <div
            v-for="ep in ctrl.endpoints"
            :key="ep.endpointId"
            class="endpoint-item"
            :class="{ active: activeEndpointId === ep.endpointId }"
            @click="emit('select-endpoint', ep.endpointId, ep)"
          >
            <el-tag :type="methodTagType(ep.method)" size="small" class="method-tag">
              {{ ep.method }}
            </el-tag>
            <span class="ep-path">{{ ep.fullPath }}</span>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-scrollbar>
  </div>
</template>

<style scoped>
.empty-tip {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.project-info {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 0 12px;
  font-weight: 600;
  font-size: 14px;
  border-bottom: 1px solid #f0f0f0;
  margin-bottom: 8px;
}

.ctrl-name {
  font-weight: 600;
  font-size: 13px;
  margin-right: 8px;
}

.endpoint-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  cursor: pointer;
  border-radius: 4px;
  font-size: 13px;
  transition: background 0.2s;
}

.endpoint-item:hover {
  background: #f5f7fa;
}

.endpoint-item.active {
  background: #ecf5ff;
  color: #409eff;
}

.method-tag {
  min-width: 50px;
  text-align: center;
}

.ep-path {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
