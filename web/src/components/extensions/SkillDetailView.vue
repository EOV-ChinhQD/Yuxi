<template>
  <div class="skill-detail extension-detail-page">
    <div v-if="loading" class="loading-bar-wrapper">
      <div class="loading-bar"></div>
    </div>
    <div class="detail-top-bar">
      <button class="detail-back-btn" @click="goBack">
        <ArrowLeft :size="16" />
        <span>Trở lại</span>
      </button>
      <div class="detail-title-area">
        <div class="detail-icon">
          <BookMarked :size="18" />
        </div>
        <div class="detail-title-text">
          <h2>{{ currentSkill?.name || slug }}</h2>
          <span class="detail-subtitle">{{ currentSkillStatusLabel }}</span>
        </div>
      </div>
      <div class="detail-actions">
        <a-space :size="8">
          <button
            v-if="isInstalledSkill && canManageCurrentSkill"
            type="button"
            @click="handleExport"
            class="lucide-icon-btn extension-panel-action extension-panel-action-secondary"
          >
            <Download :size="14" />
            <span>Xuất khẩu</span>
          </button>
          <button
            v-if="isInstalledSkill && canManageCurrentSkill && !isBuiltinInstalledSkill"
            type="button"
            @click="confirmDeleteSkill"
            class="lucide-icon-btn extension-panel-action extension-panel-action-danger"
          >
            <Trash2 :size="14" />
            <span>Xóa</span>
          </button>
        </a-space>
      </div>
    </div>

    <div class="detail-content-wrapper">
      <div v-if="currentSkill" class="detail-content-inner">
        <div v-if="isReadOnlySkill" class="readonly-scope-hint readonly-detail-hint">
          Bạn có thể xem và sử dụng cái này Skill，nhưng không có quyền quản trị。
        </div>
        <a-tabs v-if="isInstalledSkill" v-model:activeKey="activeTab" class="minimal-tabs">
          <a-tab-pane key="editor">
            <template #tab>
              <span class="tab-title"><FileText :size="14" />Quản lý mã</span>
            </template>
            <div class="workspace">
              <div class="tree-container">
                <div class="tree-header">
                  <span class="label">Cấu trúc dự án</span>
                  <div class="tree-actions">
                    <a-tooltip v-if="canEditSkillFiles" title="Tạo tập tin mới"
                      ><button @click="openCreateModal(false)"><FilePlus :size="14" /></button
                    ></a-tooltip>
                    <a-tooltip v-if="canEditSkillFiles" title="Tạo thư mục mới"
                      ><button @click="openCreateModal(true)"><FolderPlus :size="14" /></button
                    ></a-tooltip>
                    <a-tooltip title="Làm mới"
                      ><button @click="reloadTree"><RotateCw :size="14" /></button
                    ></a-tooltip>
                  </div>
                </div>
                <div class="tree-content">
                  <FileTreeComponent
                    v-model:selectedKeys="selectedTreeKeys"
                    v-model:expandedKeys="expandedKeys"
                    :tree-data="treeData"
                    @select="handleTreeSelect"
                  />
                </div>
              </div>
              <div class="editor-container">
                <div class="editor-main">
                  <a-empty
                    v-if="!selectedPath || selectedIsDir"
                    description="Chọn tập tin để bắt đầu chỉnh sửa"
                    class="mt-40"
                  />
                  <template v-else>
                    <AgentFilePreview
                      :file="selectedFilePreview"
                      :file-path="selectedPath"
                      :show-download="false"
                      :show-fullscreen="true"
                      :editable="canEditSkillFiles"
                      :edit-all-text="true"
                      :saving="savingFile"
                      :full-height="true"
                      container-class="skill-file-preview"
                      content-class="skill-file-preview-content"
                      @save="saveCurrentFile"
                    />
                  </template>
                </div>
              </div>
            </div>
          </a-tab-pane>

          <a-tab-pane key="settings">
            <template #tab>
              <span class="tab-title"><Settings :size="14" />Phạm vi hiệu quả</span>
            </template>
            <div class="config-view">
              <div class="config-header">
                <div class="text">
                  <h3>Trạng thái chia sẻ và kích hoạt</h3>
                  <p>
                    kiểm soát việc này Skill Nó có sẵn không，và người dùng nào có thể chọn và chạy
                    nó。
                  </p>
                </div>
                <a-button
                  v-if="canManageCurrentSkill"
                  type="primary"
                  :loading="savingShareConfig"
                  @click="saveShareConfig"
                  class="lucide-icon-btn"
                >
                  <Save :size="14" />
                  <span>Lưu cài đặt</span>
                </a-button>
              </div>
              <div class="settings-stack">
                <section class="settings-card">
                  <div class="settings-card-main">
                    <div class="settings-card-title">Trạng thái đã bật</div>
                    <div class="settings-card-desc">
                      Sau khi vô hiệu hóa tính năng này Skill Sẽ không xuất hiện trong các tài
                      nguyên tùy chọn，Sẽ không tham gia Agent Tải khi chạy。
                    </div>
                  </div>
                  <div class="settings-card-action">
                    <span class="status-pill" :class="enabledForm ? 'enabled' : 'disabled'">
                      {{ enabledForm ? 'Đã bật' : 'Đã tắt' }}
                    </span>
                    <a-switch v-model:checked="enabledForm" :disabled="!canManageCurrentSkill" />
                  </div>
                </section>

                <section class="settings-card scope-card">
                  <div class="settings-card-main">
                    <div class="settings-card-title">Phạm vi hiệu quả</div>
                    <div class="settings-card-desc">
                      Kiểm soát những người dùng nào có thể chọn và sử dụng cái này trong thời gian
                      chạy Skill。
                    </div>
                  </div>
                  <div v-if="isBuiltinInstalledSkill" class="readonly-scope-hint">
                    Tích hợp sẵn Skill Đã sửa lỗi cho phạm vi hiệu quả toàn cầu，Việc có tham gia
                    vào thời gian chạy hay không có thể được kiểm soát bằng cách bật trạng thái。
                  </div>
                  <div v-else-if="isReadOnlySkill" class="readonly-scope-hint">
                    hiện tại Skill Chỉ đọc cho bạn，Phạm vi hiệu quả không thể được sửa đổi。
                  </div>
                  <ShareConfigForm
                    v-else
                    ref="shareConfigFormRef"
                    v-model="shareConfigForm"
                    :auto-select-user-dept="true"
                    :allowed-access-levels="allowedSkillAccessLevels"
                  />
                </section>
              </div>
            </div>
          </a-tab-pane>

          <a-tab-pane key="dependencies">
            <template #tab>
              <span class="tab-title"><Layers :size="14" />Quản lý phụ thuộc</span>
            </template>
            <div class="config-view">
              <div class="config-header">
                <div class="text">
                  <h3>Tuyên bố phụ thuộc</h3>
                  <p>
                    cấu hình cái này Skill công cụ cần thiết、MCP và những người khác Skill phụ
                    thuộc vào。
                  </p>
                </div>
                <a-button
                  v-if="canEditSkillDependencies"
                  type="primary"
                  :loading="savingDependencies"
                  @click="saveDependencies"
                  class="lucide-icon-btn"
                >
                  <Save :size="14" />
                  <span>Cập nhật phần phụ thuộc</span>
                </a-button>
              </div>
              <div class="dependency-groups">
                <section
                  v-for="group in dependencyGroups"
                  :key="group.key"
                  class="dependency-card"
                  :class="{ readonly: !canEditSkillDependencies }"
                >
                  <div class="dependency-card-header">
                    <div class="dependency-title-block">
                      <div class="dependency-title-row">
                        <h4>{{ group.title }}</h4>
                        <span class="dependency-count"
                          >Đã chọn {{ getDependencyValues(group).length }} mục</span
                        >
                      </div>
                      <p>{{ group.description }}</p>
                    </div>
                    <a-dropdown
                      v-if="canEditSkillDependencies"
                      :trigger="['click']"
                      placement="bottomRight"
                      overlay-class-name="dependency-selection-popover"
                    >
                      <a-button size="small" class="dependency-action-btn dependency-select-btn">
                        <Plus :size="13" />
                        <span>Chọn phần phụ thuộc</span>
                        <ChevronDown :size="12" class="dependency-select-chevron" />
                      </a-button>
                      <template #overlay>
                        <div class="selection-dropdown" @mousedown.stop @click.stop>
                          <div class="selection-dropdown-header">
                            <div class="selection-dropdown-title">{{ group.title }}</div>
                            <div class="selection-dropdown-subtitle">{{ group.dropdownHint }}</div>
                          </div>
                          <a-input
                            v-model:value="dependencySearch[group.key]"
                            size="small"
                            allow-clear
                            class="selection-search"
                            :placeholder="`Tìm kiếm${group.shortTitle}`"
                            @mousedown.stop
                            @click.stop
                          />
                          <div
                            v-if="getFilteredDependencyOptions(group).length"
                            class="selection-list"
                          >
                            <div
                              v-for="option in getFilteredDependencyOptions(group)"
                              :key="option.value"
                              role="checkbox"
                              :aria-checked="isDependencySelected(group, option.value)"
                              tabindex="0"
                              class="selection-item"
                              :class="{ selected: isDependencySelected(group, option.value) }"
                              @mousedown.stop
                              @click.stop="
                                toggleDependency(
                                  group,
                                  option.value,
                                  !isDependencySelected(group, option.value)
                                )
                              "
                              @keydown.enter.prevent="
                                toggleDependency(
                                  group,
                                  option.value,
                                  !isDependencySelected(group, option.value)
                                )
                              "
                              @keydown.space.prevent="
                                toggleDependency(
                                  group,
                                  option.value,
                                  !isDependencySelected(group, option.value)
                                )
                              "
                            >
                              <span class="selection-item-content">
                                <a-checkbox
                                  :checked="isDependencySelected(group, option.value)"
                                  @click.stop
                                  @change="
                                    toggleDependency(group, option.value, $event.target.checked)
                                  "
                                />
                                <span class="selection-label">{{ option.label }}</span>
                              </span>
                            </div>
                          </div>
                          <div v-else class="selection-empty">
                            {{
                              group.options.length
                                ? 'Không có sự phụ thuộc phù hợp'
                                : 'Chưa có phụ thuộc tùy chọn nào'
                            }}
                          </div>
                        </div>
                      </template>
                    </a-dropdown>
                    <a-button v-else size="small" disabled class="dependency-action-btn">
                      {{ isBuiltinInstalledSkill ? 'Bảo trì hệ thống' : 'chỉ đọc' }}
                    </a-button>
                  </div>

                  <div v-if="getDependencyValues(group).length" class="dependency-chip-list">
                    <span
                      v-for="value in getDependencyValues(group)"
                      :key="value"
                      class="dependency-chip"
                      :title="getDependencyOptionLabel(group, value)"
                    >
                      <span>{{ getDependencyOptionLabel(group, value) }}</span>
                      <button
                        v-if="canEditSkillDependencies"
                        type="button"
                        class="dependency-chip-remove"
                        :aria-label="`Xóa ${getDependencyOptionLabel(group, value)}`"
                        @click="removeDependency(group, value)"
                      >
                        <X :size="12" />
                      </button>
                    </span>
                  </div>
                  <div v-else class="dependency-empty-hint">{{ group.emptyText }}</div>
                </section>
              </div>
            </div>
          </a-tab-pane>
        </a-tabs>
      </div>
      <div v-else-if="!loading" class="detail-empty">
        <a-empty description="không tìm thấy Skill" />
      </div>
    </div>

    <a-modal
      v-model:open="createModalVisible"
      :title="createForm.isDir ? 'Tạo thư mục mới' : 'Tạo tập tin mới'"
      @ok="handleCreateNode"
      :confirm-loading="creatingNode"
      width="400px"
    >
      <a-form layout="vertical" class="pt-12">
        <a-form-item label="con đường (Liên quan đến thư mục gốc)" required>
          <a-input v-model:value="createForm.path" placeholder="src/main.py" />
        </a-form-item>
        <a-form-item v-if="!createForm.isDir" label="nội dung">
          <a-textarea v-model:value="createForm.content" :rows="5" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import {
  ArrowLeft,
  BookMarked,
  Download,
  Trash2,
  Save,
  FileText,
  Layers,
  FilePlus,
  FolderPlus,
  RotateCw,
  Settings,
  X,
  Plus,
  ChevronDown
} from 'lucide-vue-next'
import { skillApi } from '@/apis/skill_api'
import AgentFilePreview from '@/components/AgentFilePreview.vue'
import FileTreeComponent from '@/components/FileTreeComponent.vue'
import ShareConfigForm from '@/components/ShareConfigForm.vue'

const route = useRoute()
const router = useRouter()
const slug = computed(() => decodeURIComponent(route.params.slug))

const loading = ref(false)
const currentSkill = ref(null)
const treeData = ref([])
const selectedTreeKeys = ref([])
const expandedKeys = ref([])
const selectedPath = ref('')
const selectedIsDir = ref(false)
const fileContent = ref('')
const savingFile = ref(false)
const creatingNode = ref(false)
const savingDependencies = ref(false)
const savingShareConfig = ref(false)
const activeTab = ref('editor')

const skills = ref([])
const createModalVisible = ref(false)
const createForm = reactive({ path: '', isDir: false, content: '' })
const allowedSkillAccessLevels = ref(['user'])
const enabledForm = ref(true)
const shareConfigFormRef = ref(null)
const shareConfigForm = ref({ access_level: 'user', department_ids: [], user_uids: [] })
const dependencyOptions = reactive({ tools: [], mcps: [], skills: [] })
const dependencyForm = reactive({
  tool_dependencies: [],
  mcp_dependencies: [],
  skill_dependencies: []
})
const dependencySearch = reactive({ tools: '', mcps: '', skills: '' })

const isInstalledSkill = computed(() => !!currentSkill.value?.dir_path)

const isBuiltinInstalledSkill = computed(() => {
  return !!(isInstalledSkill.value && currentSkill.value?.source_type === 'builtin')
})
const canManageCurrentSkill = computed(() => currentSkill.value?.can_manage !== false)
const isReadOnlySkill = computed(() => isInstalledSkill.value && !canManageCurrentSkill.value)
const canEditSkillFiles = computed(
  () => canManageCurrentSkill.value && !isBuiltinInstalledSkill.value
)
const canEditSkillDependencies = computed(
  () => canManageCurrentSkill.value && !isBuiltinInstalledSkill.value
)

const sourceTypeLabel = (sourceType) => {
  if (sourceType === 'builtin') return 'Tích hợp sẵn'
  if (sourceType === 'remote') return 'Thêm từ xa'
  return 'tải lên'
}

const currentSkillStatusLabel = computed(() => {
  const skill = currentSkill.value
  if (!skill) return ''
  if (skill.enabled === false) return `${sourceTypeLabel(skill.source_type)} · Đã tắt`
  return sourceTypeLabel(skill.source_type)
})

const selectedFilePreview = computed(() => ({
  content: fileContent.value,
  previewType: 'text',
  supported: true
}))

const toolDependencyOptions = computed(() =>
  (dependencyOptions.tools || []).map((i) =>
    typeof i === 'object'
      ? { label: i.name || i.slug, value: i.slug || i.id }
      : { label: i, value: i }
  )
)
const mcpDependencyOptions = computed(() =>
  (dependencyOptions.mcps || []).map((i) => ({ label: i, value: i }))
)
const skillDependencyOptions = computed(() =>
  (dependencyOptions.skills || [])
    .filter((s) => s !== currentSkill.value?.slug)
    .map((i) => ({ label: i, value: i }))
)

const dependencyGroups = computed(() => [
  {
    key: 'tools',
    formKey: 'tool_dependencies',
    title: 'Phụ thuộc công cụ',
    shortTitle: 'Công cụ',
    description: 'tuyên bố điều này Skill Các khả năng của công cụ cần được gọi khi chạy。',
    dropdownHint: 'Sau khi lựa chọn Agent Những công cụ này sẽ được tải khi chạy。',
    emptyText: 'Phần phụ thuộc của công cụ không được khai báo',
    options: toolDependencyOptions.value
  },
  {
    key: 'mcps',
    formKey: 'mcp_dependencies',
    title: 'MCP phụ thuộc vào',
    shortTitle: 'MCP',
    description: 'tuyên bố điều này Skill phụ thuộc MCP dịch vụ。',
    dropdownHint: 'chọn cái này Skill Bắt buộc trong thời gian chạy MCP dịch vụ。',
    emptyText: 'Không khai báo MCP phụ thuộc vào',
    options: mcpDependencyOptions.value
  },
  {
    key: 'skills',
    formKey: 'skill_dependencies',
    title: 'Skill phụ thuộc vào',
    shortTitle: 'Skill',
    description: 'Khai báo các mục khác cần được nạp cùng nhau Skill。',
    dropdownHint:
      'phụ thuộc vào Skill sẽ đi theo hiện tại Skill Nhập phạm vi có thể đọc được trong thời gian chạy cùng nhau。',
    emptyText: 'Không khai báo Skill phụ thuộc vào',
    options: skillDependencyOptions.value
  }
])

const getDependencyValues = (group) => dependencyForm[group.formKey] || []

const getDependencyOptionLabel = (group, value) => {
  const option = group.options.find((item) => item.value === value)
  return option?.label || value
}

const getFilteredDependencyOptions = (group) => {
  const keyword = String(dependencySearch[group.key] || '')
    .trim()
    .toLowerCase()
  if (!keyword) return group.options
  return group.options.filter((option) => {
    const label = String(option.label || '').toLowerCase()
    const value = String(option.value || '').toLowerCase()
    return label.includes(keyword) || value.includes(keyword)
  })
}

const isDependencySelected = (group, value) => getDependencyValues(group).includes(value)

const toggleDependency = (group, value, checked) => {
  if (!canEditSkillDependencies.value) return
  const values = getDependencyValues(group)
  if (checked) {
    if (!values.includes(value)) dependencyForm[group.formKey] = [...values, value]
    return
  }
  dependencyForm[group.formKey] = values.filter((item) => item !== value)
}

const removeDependency = (group, value) => {
  toggleDependency(group, value, false)
}

const goBack = () => {
  router.push({ path: '/extensions', query: { tab: 'skills' } })
}

const cloneShareConfig = (config) => ({
  access_level: config?.access_level || 'user',
  department_ids: [...(config?.department_ids || [])],
  user_uids: [...(config?.user_uids || [])]
})

const syncShareConfigFromSkill = (skillRecord) => {
  enabledForm.value = skillRecord?.enabled !== false
  shareConfigForm.value = cloneShareConfig(skillRecord?.share_config)
}

const fetchSkillDetail = async () => {
  loading.value = true
  try {
    const skillResult = await skillApi.listSkills()
    skills.value = skillResult?.data || []
    allowedSkillAccessLevels.value = skillResult?.allowed_access_levels || ['user']

    const found = skills.value.find((s) => s.slug === slug.value)
    if (found) {
      currentSkill.value = found
      syncDependencyFormFromSkill(found)
      syncShareConfigFromSkill(found)
      await reloadTree()
      await loadSkillFile(found.slug)
    }
    await fetchDependencyOptions(currentSkill.value?.slug)
  } catch {
    message.error('Tải không thành công')
  } finally {
    loading.value = false
  }
}

const fetchDependencyOptions = async (currentSlug) => {
  try {
    const result = await skillApi.getSkillDependencyOptions(currentSlug)
    const data = result?.data || {}
    dependencyOptions.tools = data.tools || []
    dependencyOptions.mcps = data.mcps || []
    dependencyOptions.skills = data.skills || []
  } catch {
    // ignore
  }
}

const syncDependencyFormFromSkill = (skillRecord) => {
  dependencyForm.tool_dependencies = [...(skillRecord?.tool_dependencies || [])]
  dependencyForm.mcp_dependencies = [...(skillRecord?.mcp_dependencies || [])]
  dependencyForm.skill_dependencies = [...(skillRecord?.skill_dependencies || [])]
}

const normalizeTree = (nodes) =>
  (nodes || []).map((node) => ({
    title: node.name,
    key: node.path,
    isLeaf: !node.is_dir,
    path: node.path,
    is_dir: node.is_dir,
    children: node.is_dir ? normalizeTree(node.children || []) : undefined
  }))

const resetFileState = () => {
  selectedPath.value = ''
  selectedIsDir.value = false
  selectedTreeKeys.value = []
  expandedKeys.value = []
  fileContent.value = ''
}

const expandAllKeys = (nodes) =>
  nodes.flatMap((node) => (node.is_dir ? [node.key, ...expandAllKeys(node.children || [])] : []))

const reloadTree = async () => {
  if (!currentSkill.value || !isInstalledSkill.value) return
  loading.value = true
  try {
    const result = await skillApi.getSkillTree(currentSkill.value.slug)
    const normalized = normalizeTree(result?.data || [])
    treeData.value = normalized
    expandedKeys.value = expandAllKeys(normalized)
  } catch {
    message.error('Không tải được cây thư mục')
  } finally {
    loading.value = false
  }
}

const loadSkillFile = async (skillSlug, path = 'SKILL.md') => {
  try {
    const fileResult = await skillApi.getSkillFile(skillSlug, path)
    const content = fileResult?.data?.content || ''
    fileContent.value = content
    selectedPath.value = path
    selectedIsDir.value = false
    selectedTreeKeys.value = [path]
  } catch {
    // file not found is ok
  }
}

const handleTreeSelect = async (keys, info) => {
  if (!keys?.length) {
    resetFileState()
    return
  }
  const node = info?.node || {}
  const path = node.path || node.key
  const isDir = !!node.is_dir
  selectedTreeKeys.value = [path]
  selectedPath.value = path
  selectedIsDir.value = isDir
  if (isDir) {
    fileContent.value = ''
    return
  }
  try {
    const result = await skillApi.getSkillFile(currentSkill.value.slug, path)
    const content = result?.data?.content || ''
    fileContent.value = content
  } catch {
    message.error('Đọc tệp không thành công')
  }
}

const saveCurrentFile = async (content = fileContent.value) => {
  if (!currentSkill.value || !selectedPath.value || selectedIsDir.value || !canEditSkillFiles.value)
    return
  savingFile.value = true
  try {
    await skillApi.updateSkillFile(currentSkill.value.slug, {
      path: selectedPath.value,
      content
    })
    fileContent.value = content
    message.success('đã lưu')
    if (selectedPath.value === 'SKILL.md') await fetchSkillDetail()
  } catch {
    message.error('Lưu không thành công')
  } finally {
    savingFile.value = false
  }
}

const confirmDeleteSkill = () => {
  const target = currentSkill.value
  if (!target || !canManageCurrentSkill.value || isBuiltinInstalledSkill.value) return
  const actionText = 'Xóa'
  Modal.confirm({
    title: `Xác nhận${actionText}Kỹ năng「${target.slug}」？`,
    content:
      'Không thể phục hồi sau khi xóa，Tất cả các tập tin và cấu hình sẽ biến mất vĩnh viễn。',
    okText: `Xác nhận${actionText}`,
    okType: 'danger',
    cancelText: 'Hủy bỏ',
    onOk: async () => {
      try {
        await skillApi.deleteSkill(target.slug)
        message.success(`Đã rồi${actionText}`)
        router.push({ path: '/extensions', query: { tab: 'skills' } })
      } catch {
        message.error(`${actionText}thất bại`)
      }
    }
  })
}

const handleExport = async () => {
  if (!currentSkill.value || !isInstalledSkill.value || !canManageCurrentSkill.value) return
  try {
    const response = await skillApi.exportSkill(currentSkill.value.slug)
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${currentSkill.value.slug}.zip`
    link.click()
    URL.revokeObjectURL(url)
  } catch {
    message.error('Xuất không thành công')
  }
}

const openCreateModal = (isDir) => {
  if (!currentSkill.value || !canEditSkillFiles.value) return
  createForm.path = ''
  createForm.content = ''
  createForm.isDir = isDir
  createModalVisible.value = true
}

const handleCreateNode = async () => {
  if (!currentSkill.value || !createForm.path.trim() || !canEditSkillFiles.value) return
  creatingNode.value = true
  try {
    await skillApi.createSkillFile(currentSkill.value.slug, {
      path: createForm.path.trim(),
      is_dir: createForm.isDir,
      content: createForm.content
    })
    createModalVisible.value = false
    await reloadTree()
    message.success('Đã tạo thành công')
  } catch {
    message.error('Tạo không thành công')
  } finally {
    creatingNode.value = false
  }
}

const saveShareConfig = async () => {
  if (!currentSkill.value || !isInstalledSkill.value || !canManageCurrentSkill.value) return
  if (!isBuiltinInstalledSkill.value) {
    const validation = shareConfigFormRef.value?.validate?.()
    if (validation && !validation.valid) {
      message.warning(validation.message || 'Hãy cải thiện Skill Phạm vi hiệu quả')
      return
    }
  }

  savingShareConfig.value = true
  try {
    if (!isBuiltinInstalledSkill.value) {
      await skillApi.updateSkillShareConfig(currentSkill.value.slug, shareConfigForm.value)
    }
    const result = await skillApi.updateSkillEnabled(currentSkill.value.slug, enabledForm.value)
    if (result?.data) {
      currentSkill.value = result.data
      syncShareConfigFromSkill(result.data)
    }
    message.success('Đã lưu cài đặt')
  } catch (error) {
    message.error(error?.response?.data?.detail || error.message || 'Không lưu được cài đặt')
  } finally {
    savingShareConfig.value = false
  }
}

const saveDependencies = async () => {
  if (!currentSkill.value || !isInstalledSkill.value || !canEditSkillDependencies.value) return
  savingDependencies.value = true
  try {
    const result = await skillApi.updateSkillDependencies(currentSkill.value.slug, {
      tool_dependencies: dependencyForm.tool_dependencies,
      mcp_dependencies: dependencyForm.mcp_dependencies,
      skill_dependencies: dependencyForm.skill_dependencies
    })
    const updated = result?.data
    if (updated) {
      currentSkill.value = updated
      syncDependencyFormFromSkill(updated)
    }
    await fetchSkillDetail()
    message.success('Các phần phụ thuộc đã được cập nhật')
  } catch {
    message.error('Cập nhật không thành công')
  } finally {
    savingDependencies.value = false
  }
}

onMounted(() => {
  fetchSkillDetail()
})
</script>

<style lang="less" scoped>
@import '@/assets/css/extensions.less';
@import '@/assets/css/extension-detail.less';

.skill-detail {
  .detail-content-wrapper {
    flex: 1;
    min-height: 0;
    overflow: hidden;
    background-color: var(--gray-10);
  }

  .detail-content-inner {
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  :deep(.minimal-tabs) {
    height: 100%;
  }
}

.workspace {
  display: flex;
  flex: 1;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.tree-container {
  width: 240px;
  border-right: 1px solid var(--gray-150);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;

  .tree-header {
    padding: 10px var(--page-padding) 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    .label {
      font-size: 12px;
      font-weight: 600;
      color: var(--gray-500);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .tree-actions {
      display: flex;
      gap: 4px;
      button {
        background: none;
        border: none;
        padding: 2px;
        cursor: pointer;
        color: var(--gray-500);
        display: flex;
        align-items: center;
        &:hover {
          color: var(--gray-900);
        }
      }
    }
  }

  .tree-content {
    flex: 1;
    overflow-y: auto;
    height: 100%;
    padding: 8px calc(var(--page-padding) - 4px);
  }
}

.editor-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;

  .editor-main {
    flex: 1;
    min-height: 0;
    background-color: var(--gray-0);
    display: flex;
    flex-direction: column;
  }

  .editor-main :deep(.ant-empty) {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .skill-file-preview {
    flex: 1;
    min-height: 0;
    border-radius: 0;
  }

  :deep(.skill-file-preview-content) {
    flex: 1;
    min-height: 0;
    max-height: none;
  }

  :deep(.skill-file-preview-content .file-content-pre.code-highlight code) {
    min-height: 100%;
  }
}

.config-view {
  padding: 20px;
  flex: 1;
  overflow-y: auto;
  max-width: 860px;

  .config-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 18px;
    flex-shrink: 0;

    .text {
      h3 {
        margin: 0 0 4px 0;
        font-size: 16px;
        font-weight: 600;
        color: var(--gray-900);
      }

      p {
        margin: 0;
        color: var(--gray-500);
        font-size: 13px;
      }
    }
  }
}

.settings-stack,
.dependency-groups {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.settings-card,
.dependency-card {
  border: 1px solid var(--gray-150);
  border-radius: 10px;
  background: var(--gray-0);
}

.settings-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 12px;

  &.scope-card {
    display: block;
  }
}

.settings-card-main {
  min-width: 0;
}

.settings-card-title {
  margin-bottom: 4px;
  color: var(--gray-900);
  font-size: 14px;
  font-weight: 700;
}

.settings-card-desc {
  color: var(--gray-500);
  font-size: 13px;
  line-height: 1.55;
}

.settings-card-action {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  gap: 10px;
}

.scope-card .settings-card-main {
  margin-bottom: 14px;
}

.status-pill {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  line-height: 18px;

  &.enabled {
    background: var(--main-10);
    color: var(--main-color);
  }

  &.disabled {
    background: var(--gray-100);
    color: var(--gray-500);
  }
}

.readonly-scope-hint {
  color: var(--gray-500);
  background: var(--gray-50);
  border: 1px solid var(--gray-150);
  border-radius: 10px;
  padding: 11px 12px;
  font-size: 13px;
  line-height: 1.55;
}

.dependency-card {
  padding: 14px;

  &.readonly {
    background: linear-gradient(180deg, var(--gray-0) 0%, var(--gray-25) 100%);
  }
}

.dependency-card-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.dependency-title-block {
  min-width: 0;
  flex: 1;
}

.dependency-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;

  h4 {
    margin: 0;
    color: var(--gray-900);
    font-size: 14px;
    font-weight: 700;
  }
}

.dependency-title-block p {
  margin: 4px 0 0;
  color: var(--gray-500);
  font-size: 12px;
  line-height: 1.45;
}

.dependency-count {
  padding: 1px 7px;
  border-radius: 999px;
  background: var(--gray-50);
  color: var(--gray-500);
  font-size: 12px;
  line-height: 18px;
}

.dependency-action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 30px;
  flex-shrink: 0;
  gap: 5px;
  padding: 0 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}

.dependency-select-btn {
  border-color: var(--gray-100);
  background: var(--gray-50);
  box-shadow: 0 1px 3px rgb(0 0 0 / 3%);

  &:hover,
  &:focus {
    border-color: var(--main-color);
    background: var(--main-20);
    color: var(--main-color);
  }
}

.dependency-select-chevron {
  opacity: 0.72;
}

.dependency-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.dependency-chip {
  display: inline-flex;
  align-items: center;
  max-width: 220px;
  gap: 6px;
  padding: 4px 8px;
  border: 1px solid var(--gray-150);
  border-radius: 6px;
  background: var(--gray-50);
  color: var(--gray-700);
  font-size: 12px;
  line-height: 18px;

  span {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.dependency-chip-remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--gray-500);
  cursor: pointer;

  &:hover {
    background: var(--gray-150);
    color: var(--gray-800);
  }
}

.dependency-empty-hint {
  margin-top: 14px;
  padding: 10px 12px;
  border: 1px dashed var(--gray-150);
  border-radius: 6px;
  background: var(--gray-25);
  color: var(--gray-500);
  font-size: 12px;
}

@media (max-width: 768px) {
  .config-view {
    padding: 14px;
  }

  .config-header,
  .settings-card,
  .dependency-card-header {
    flex-direction: column;
    align-items: stretch;
  }

  .dependency-chip-list,
  .dependency-empty-hint {
    margin-left: 0;
    padding-left: 0;
  }
}

.mt-40 {
  margin-top: 40px;
}
.pt-12 {
  padding-top: 12px;
}
</style>

<style lang="less">
.dependency-selection-popover {
  .selection-dropdown {
    width: 300px;
    max-height: 360px;
    padding: 8px;
    overflow: hidden auto;
    border: 1px solid var(--gray-200);
    border-radius: 14px;
    background: var(--gray-0);
    box-shadow: 0 8px 22px rgb(0 0 0 / 8%);
  }

  .selection-dropdown-header {
    padding: 8px 10px 10px;
    margin-bottom: 4px;
    border-bottom: 1px solid var(--gray-100);
  }

  .selection-dropdown-title {
    color: var(--gray-900);
    font-size: 13px;
    font-weight: 700;
    line-height: 1.4;
  }

  .selection-dropdown-subtitle {
    margin-top: 2px;
    color: var(--gray-500);
    font-size: 12px;
    line-height: 1.4;
  }

  .selection-search {
    width: calc(100% - 16px);
    height: 30px;
    margin: 8px;
  }

  .selection-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .selection-item {
    display: flex;
    align-items: center;
    min-height: 38px;
    gap: 8px;
    padding: 8px 10px;
    border-radius: 9px;
    color: var(--gray-800);
    cursor: pointer;
    transition:
      background-color 160ms ease,
      color 160ms ease;

    &:hover {
      background: var(--gray-50);
    }

    &.selected {
      background: var(--main-10);
      color: var(--gray-900);
    }
  }

  .selection-item-content {
    display: flex;
    align-items: center;
    min-width: 0;
    gap: 8px;
  }

  .selection-label {
    min-width: 0;
    overflow: hidden;
    font-size: 13px;
    line-height: 18px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .selection-empty {
    display: block;
    padding: 16px 0;
    color: var(--gray-600);
    font-size: 13px;
    text-align: center;
  }
}
</style>
