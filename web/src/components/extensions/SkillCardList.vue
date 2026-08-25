<template>
  <div class="skill-cards-page extension-page-root">
    <PageShoulder search-placeholder="Tìm kiếm kỹ năng..." v-model:search="searchQuery">
      <template #actions>
        <template v-if="!isBatchDeleteMode">
          <a-button
            @click="isBatchDeleteMode = true"
            :disabled="loading || importing || filteredDeletableSkills.length === 0"
            class="lucide-icon-btn"
          >
            <span>Quản lý hàng loạt</span>
          </a-button>
          <a-button
            @click="handleOpenRemoteInstall"
            :disabled="loading || importing"
            class="lucide-icon-btn"
          >
            <Computer :size="14" />
            <span>Cài đặt từ xa</span>
          </a-button>
          <a-upload
            accept=".zip,.md"
            :show-upload-list="false"
            :custom-request="handleImportUpload"
            :before-upload="beforeSkillUpload"
            :disabled="loading || importing"
          >
            <a-button type="primary" :loading="importing" class="lucide-icon-btn">
              <Upload :size="14" />
              <span>Tải lên Skill</span>
            </a-button>
          </a-upload>
          <a-tooltip title="Làm mới Skills" placement="bottom">
            <a-button
              class="lucide-icon-btn"
              aria-label="Làm mới Skills"
              :disabled="loading"
              @click="fetchSkills({ refreshPersonal: true })"
            >
              <RefreshCw :size="14" />
            </a-button>
          </a-tooltip>
        </template>
        <template v-else>
          <a-button size="small" type="link" @click="handleBatchSelectAll">Chọn tất cả</a-button>
          <a-button size="small" type="link" @click="handleBatchSelectInvert">Bỏ chọn</a-button>
          <a-button size="small" type="link" @click="handleBatchSelectNone">Xóa trắng</a-button>
          <a-button
            type="primary"
            danger
            :disabled="selectedCardSlugs.length === 0"
            :loading="loading"
            @click="handleBatchDelete"
          >
            Xóa hàng loạt ({{ selectedCardSlugs.length }})
          </a-button>
          <a-button :disabled="loading" @click="exitBatchDeleteMode">Thoát quản lý</a-button>
        </template>
      </template>
    </PageShoulder>

    <div
      v-if="visibleSkillGroups.length === 0"
      class="extension-card-grid-empty-state skill-empty-state"
    >
      <div class="skill-empty-card">
        <div class="skill-empty-icon">
          <WandSparkles :size="22" />
        </div>
        <div class="skill-empty-title">
          {{ searchQuery ? 'Không tìm thấy Skill' : 'Chưa có Skill nào' }}
        </div>
        <div class="skill-empty-desc">
          {{
            searchQuery
              ? 'Thử từ khóa khác hoặc xóa điều kiện tìm kiếm.'
              : 'Có thể cài đặt từ kho lưu trữ từ xa, hoặc tải lên tệp Skill cục bộ.'
          }}
        </div>
      </div>
    </div>

    <template v-else>
      <template v-for="group in visibleSkillGroups" :key="group.key">
        <div class="extension-section-header">{{ group.title }}</div>
        <ExtensionCardGrid :min-width="280">
          <div
            v-for="skill in group.skills"
            :key="`${group.key}:${skill.slug || skill.id}`"
            class="card-wrapper"
            :class="{
              selected: !skill.isSuite && selectedCardSlugs.includes(skill.slug),
              'batch-mode': isBatchDeleteMode && !skill.isSuite
            }"
          >
            <SkillSuiteCard
              v-if="skill.isSuite"
              :suite="skill"
              :installed-slugs="[...installedPersonalSkillKeys]"
              @open="openRecommendedSuite"
            />
            <template v-else>
              <a-checkbox
                v-if="
                  isBatchDeleteMode &&
                  canManageSkill(skill) &&
                  skill.sourceType !== 'builtin' &&
                  skill.sourceScope !== 'personal'
                "
                :checked="selectedCardSlugs.includes(skill.slug)"
                @change="handleToggleCardSelect(skill.slug)"
                class="card-select-checkbox"
              />
              <InfoCard
                variant="default"
                :title="formatExtensionCardTitle(skill.name)"
                :subtitle="skill.slug"
                :description="skill.description || 'Không có mô tả'"
                :tags="skillCardTags(skill)"
                :default-icon="getSkillIcon(skill.slug)"
                @click="handleCardClick(skill)"
                :class="{ 'card-clickable-select': isBatchDeleteMode }"
              >
                <template #actions>
                  <button
                    v-if="skill.sourceScope !== 'personal'"
                    type="button"
                    class="skill-enabled-action"
                    :class="{ enabled: skill.enabled !== false }"
                    :disabled="!canManageSkill(skill) || isSkillToggling(skill.slug)"
                    :aria-label="skill.enabled === false ? 'Bật Skill' : 'Tắt Skill'"
                    @click.stop="handleToggleSkillEnabled(skill)"
                  >
                    <Plus v-if="skill.enabled === false" :size="15" class="action-icon" />
                    <template v-else>
                      <Check :size="15" class="action-icon action-icon-check" />
                      <Minus :size="15" class="action-icon action-icon-minus" />
                    </template>
                  </button>
                </template>
              </InfoCard>
            </template>
          </div>
        </ExtensionCardGrid>
      </template>
    </template>

    <a-modal
      v-model:open="skillPreviewVisible"
      class="skill-preview-modal"
      :footer="null"
      width="680px"
      :closable="false"
      :destroy-on-close="true"
      @cancel="closeSkillPreview"
    >
      <div v-if="previewSkill" class="skill-preview-panel">
        <div class="skill-preview-header">
          <div class="skill-preview-title-area">
            <div class="skill-preview-icon">
              <component :is="getSkillIcon(previewSkill.slug)" :size="18" />
            </div>
            <div class="skill-preview-title-text">
              <div class="skill-preview-title">
                {{ formatExtensionCardTitle(previewSkill.name) }}
              </div>
              <div class="skill-preview-meta">
                <span
                  >{{
                    sourceTypeLabel(previewSkill.sourceType || previewSkill.source_type)
                  }}
                  Skill</span
                >
                <span v-if="previewSkill.enabled === false" class="skill-preview-disabled-tag">
                  Đã tắt
                </span>
              </div>
            </div>
          </div>
          <div class="skill-preview-actions">
            <a-switch
              v-if="previewSkill.sourceScope !== 'personal'"
              :checked="previewSkill.enabled !== false"
              :disabled="!canManageSkill(previewSkill) || isSkillToggling(previewSkill.slug)"
              :loading="isSkillToggling(previewSkill.slug)"
              size="small"
              @change="handlePreviewToggle"
            />
          </div>
        </div>

        <div class="skill-preview-body">
          <div v-if="skillPreviewLoading" class="skill-preview-loading">
            <a-spin />
          </div>
          <MarkdownPreview
            v-else-if="skillPreviewMarkdown"
            :content="skillPreviewMarkdown"
            :compact="true"
          />
          <a-empty v-else :description="skillPreviewError || 'Không đọc được SKILL.md'" />
        </div>

        <div class="skill-preview-footer">
          <div class="skill-preview-footer-left">
            <a-button
              v-if="canDeletePreviewSkill"
              danger
              :loading="deletingPreviewSkill"
              @click="confirmDeletePreviewSkill"
            >
              Gỡ cài đặt
            </a-button>
          </div>
          <div class="skill-preview-footer-right">
            <a-button @click="closeSkillPreview">Đóng</a-button>
            <a-button
              v-if="previewSkill.sourceScope !== 'personal'"
              type="primary"
              class="lucide-icon-btn"
              @click="goToPreviewSkillManagement"
            >
              <span>Quản lý</span>
            </a-button>
          </div>
        </div>
      </div>
    </a-modal>

    <SkillInstallFlowModal
      :open="installFlowOpen"
      :flow="installFlow"
      @close="closeInstallFlow"
      @completed="handleInstallFlowCompleted"
    >
      <template #selection>
        <div class="remote-install-panel">
          <a-tabs v-model:activeKey="activeTab" class="install-tabs">
            <!-- Tab 1: Kéo từ kho lưu trữ (Repo) -->
            <a-tab-pane key="repo" tab="Kéo từ kho lưu trữ (Repo)">
              <div class="tab-content-wrapper">
                <a-form layout="vertical" class="remote-install-form">
                  <div class="repo-input-row">
                    <div class="repo-input-field">
                      <a-input
                        v-model:value="remoteInstallForm.source"
                        placeholder="Nguồn kho lưu trữ, vd: anthropics/skills hoặc GitHub URL"
                      >
                        <template #suffix>
                          <a-dropdown
                            :trigger="['click']"
                            placement="bottomRight"
                            overlay-class-name="history-dropdown-menu"
                          >
                            <div class="history-trigger-wrapper">
                              <a-tooltip title="Lịch sử kho lưu trữ">
                                <History
                                  :size="14"
                                  class="history-icon-trigger"
                                  :class="{ 'has-history': repoHistory.length > 0 }"
                                />
                              </a-tooltip>
                            </div>
                            <template #overlay>
                              <a-menu @click="handleSelectHistory">
                                <a-menu-item v-if="repoHistory.length === 0" disabled>
                                  <span class="history-empty-text">Chưa có lịch sử sử dụng</span>
                                </a-menu-item>
                                <template v-else>
                                  <a-menu-item v-for="item in repoHistory" :key="item">
                                    <div class="history-item-menu-row">
                                      <span class="history-item-text" :title="item">{{
                                        item
                                      }}</span>
                                      <span
                                        class="history-item-del-btn"
                                        @click.stop="deleteHistoryItem(item)"
                                      >
                                        <Trash2 :size="12" />
                                      </span>
                                    </div>
                                  </a-menu-item>
                                  <a-menu-divider />
                                  <a-menu-item
                                    key="clear-all-history"
                                    class="clear-history-menu-item"
                                  >
                                    <div class="clear-history-btn-content">
                                      <Trash2 :size="12" class="clear-icon" />
                                      <span>Xóa lịch sử</span>
                                    </div>
                                  </a-menu-item>
                                </template>
                              </a-menu>
                            </template>
                          </a-dropdown>
                        </template>
                      </a-input>
                    </div>
                    <a-button
                      type="primary"
                      :loading="listingRemoteSkills"
                      @click="handleListRemoteSkills"
                    >
                      Kéo kỹ năng
                    </a-button>
                  </div>
                  <div class="repo-hint-text">
                    Hỗ trợ `owner/repo` hoặc GitHub URL. Có thể truy cập
                    <a href="https://skills.sh/" target="_blank" rel="noopener noreferrer"
                      >skills.sh</a
                    >
                    để tìm kiếm các skill mã nguồn mở. Cũng hỗ trợ từng Skill từ ModelScope địa chỉ,
                    chỉ có thể cài đặt một lần：`https://modelscope.cn/skills/&lt;skill-id&gt;`。
                    Skill ID có thể lấy tại
                    <a href="https://modelscope.cn/skills" target="_blank" rel="noopener noreferrer"
                      >Chợ Skill ModelScope</a
                    >
                    sau khi vào chi tiết để lấy từ thanh địa chỉ.
                  </div>

                  <!-- Danh sách phân trang kỹ năng từ kho -->
                  <div v-if="remoteSkillOptions.length" class="skills-list-section">
                    <template v-if="hasSingleRepoSkill">
                      <div class="single-remote-skill-card">
                        <div class="single-remote-skill-name">{{ singleRepoSkill.name }}</div>
                        <div class="single-remote-skill-meta">
                          {{ singleRepoSkill.description || 'Không có mô tả' }}
                        </div>
                      </div>
                    </template>
                    <template v-else>
                      <div class="list-operations-bar">
                        <div class="op-buttons">
                          <a-button size="small" type="link" @click="handleRepoSelectAll"
                            >Chọn tất cả</a-button
                          >
                          <a-button size="small" type="link" @click="handleRepoSelectInvert"
                            >Bỏ chọn</a-button
                          >
                          <a-button size="small" type="link" @click="handleRepoSelectNone"
                            >Xóa trắng</a-button
                          >
                        </div>
                        <a-input
                          v-model:value="repoFilterKeyword"
                          placeholder="Lọc tìm kiếm cục bộ..."
                          size="small"
                          style="width: 180px"
                          allow-clear
                        />
                      </div>
                      <div class="skills-list-viewport">
                      <div class="remote-skills-list-container">
                        <div
                          v-for="item in filteredRepoSkills"
                          :key="item.name"
                          class="remote-skill-row"
                          :class="{ selected: selectedRepoSkills.includes(item.name) }"
                          role="checkbox"
                          tabindex="0"
                          :aria-checked="selectedRepoSkills.includes(item.name)"
                          @click="toggleRepoSkillFromRow(item.name)"
                          @keydown.enter.prevent="toggleRepoSkillFromRow(item.name)"
                          @keydown.space.prevent="toggleRepoSkillFromRow(item.name)"
                        >
                          <a-checkbox
                            class="remote-row-checkbox"
                            :checked="selectedRepoSkills.includes(item.name)"
                            :tabindex="-1"
                            aria-hidden="true"
                          />
                          <div class="remote-skill-row-content">
                            <span class="skill-item-name">{{ item.name }}</span>
                            <span class="skill-item-desc">{{
                              item.description || 'Không có mô tả'
                            }}</span>
                          </div>
                        </div>
                      </div>
                      </div>
                    </template>
                  </div>
                </a-form>
              </div>
            </a-tab-pane>

            <!-- Tab 2: Khám phá tìm kiếm toàn cầu -->
            <a-tab-pane key="search" tab="Khám phá tìm kiếm toàn cầu">
              <div class="tab-content-wrapper">
                <a-form layout="vertical" class="remote-install-form">
                  <div class="repo-input-row">
                    <div class="repo-input-field">
                      <a-input
                        v-model:value="searchKeyword"
                        placeholder="Nhập từ khóa như web, python để tìm kiếm"
                        @pressEnter="handleSearchRemoteSkills"
                      />
                    </div>
                    <a-button
                      type="primary"
                      :loading="searchingRemoteSkills"
                      @click="handleSearchRemoteSkills"
                    >
                      Tìm kiếm kỹ năng
                    </a-button>
                  </div>
                  <div class="repo-hint-text">
                    Nhập từ khóa để tìm kiếm các Skill mã nguồn mở trên skills.sh và tải về hàng
                    loạt.
                  </div>

                  <!-- Danh sách kết quả tìm kiếm -->
                  <div v-if="searchedSkills.length" class="skills-list-section">
                    <template v-if="hasSingleSearchedSkill">
                      <div class="single-remote-skill-card">
                        <div class="single-remote-skill-header">
                          <div class="single-remote-skill-name">
                            {{ singleSearchedSkill.name }}
                          </div>
                          <a-tag v-if="singleSearchedSkill.installs" class="skill-item-installs">
                            {{ singleSearchedSkill.installs }}
                          </a-tag>
                        </div>
                        <div class="single-remote-skill-meta">
                          {{ singleSearchedSkill.source }}
                        </div>
                      </div>
                    </template>
                    <template v-else>
                      <div class="list-operations-bar">
                        <div class="op-buttons">
                          <a-button size="small" type="link" @click="handleSearchSelectAll"
                            >Chọn tất cả</a-button
                          >
                          <a-button size="small" type="link" @click="handleSearchSelectInvert"
                            >Bỏ chọn</a-button
                          >
                          <a-button size="small" type="link" @click="handleSearchSelectNone"
                            >Xóa trắng</a-button
                          >
                        </div>
                      </div>
                      <div class="skills-list-viewport">
                      <div class="remote-skills-list-container">
                        <div
                          v-for="item in searchedSkills"
                          :key="`${item.source}:${item.name}`"
                          class="remote-skill-row"
                          :class="{ selected: isSearchSkillSelected(item) }"
                          role="checkbox"
                          tabindex="0"
                          :aria-checked="isSearchSkillSelected(item)"
                          @click="toggleSearchSkillFromRow(item)"
                          @keydown.enter.prevent="toggleSearchSkillFromRow(item)"
                          @keydown.space.prevent="toggleSearchSkillFromRow(item)"
                        >
                          <a-checkbox
                            class="remote-row-checkbox"
                            :checked="isSearchSkillSelected(item)"
                            :tabindex="-1"
                            aria-hidden="true"
                          />
                          <div class="remote-skill-row-content">
                            <span class="skill-item-name">{{ item.name }}</span>
                            <span class="skill-item-desc">{{ item.source }}</span>
                          </div>
                          <span v-if="item.installs" class="skill-install-count">
                            {{ item.installs }}
                          </span>
                        </div>
                      </div>
                      </div>
                    </template>
                  </div>
                </a-form>
              </div>
            </a-tab-pane>
          </a-tabs>
        </div>
      </template>

      <template #selection-footer>
        <span class="modal-footer-summary">{{ remoteSelectionSummary }}</span>
        <div class="modal-footer-buttons">
          <a-button @click="closeInstallFlow">Hủy</a-button>
          <a-button
            type="primary"
            :disabled="
              activeTab === 'repo'
                ? selectedRepoSkills.length === 0
                : selectedSearchSkills.length === 0
            "
            @click="startInstallRemoteSkills"
          >
            Phân tích và xác nhận
          </a-button>
        </div>
      </template>
    </SkillInstallFlowModal>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import {
  RefreshCw,
  Upload,
  Computer,
  WandSparkles,
  History,
  Trash2,
  Check,
  Plus,
  Minus
} from 'lucide-vue-next'
import { skillApi } from '@/apis/skill_api'
import ExtensionCardGrid from './ExtensionCardGrid.vue'
import SkillInstallFlowModal from './SkillInstallFlowModal.vue'
import SkillSuiteCard from './SkillSuiteCard.vue'
import InfoCard from '@/components/shared/InfoCard.vue'
import PageShoulder from '@/components/shared/PageShoulder.vue'
import MarkdownPreview from '@/components/common/MarkdownPreview.vue'
import { formatExtensionCardTitle } from '@/utils/extensionDisplayName'
import { getShareConfigLabel } from '@/utils/shareConfig'
import { getSkillIcon } from '@/utils/skill_icon_utils'

const RECOMMENDED_SUITES = [
  {
    id: 'anthropic-documents',
    name: 'Bộ kỹ năng xử lý tài liệu Anthropic',
    provider: 'Anthropic',
    description:
      'Các Skill xử lý tài liệu chính thức của Anthropic, bao gồm đọc, tạo và chỉnh sửa PDF, Word, bảng tính và bài thuyết trình.',
    source: 'anthropics/skills',
    skills: [
      {
        slug: 'pdf',
        name: 'PDF',
        description:
          'Trích xuất văn bản và bảng biểu, hỗ trợ gộp/tách, xoay và watermark, biểu mẫu, mã hóa/giải mã, trích xuất ảnh và OCR.'
      },
      {
        slug: 'docx',
        name: 'Docs',
        description:
          'Tạo và chỉnh sửa tài liệu Word, xử lý mục lục, số trang, hình ảnh, tìm kiếm và thay thế, theo dõi sửa đổi và chú thích.'
      },
      {
        slug: 'xlsx',
        name: 'XLSX',
        description:
          'Tạo và chỉnh sửa bảng tính, hỗ trợ công thức, định dạng, biểu đồ, làm sạch dữ liệu, tái cấu trúc bảng và chuyển đổi định dạng.'
      },
      {
        slug: 'pptx',
        name: 'PPTX',
        description:
          'Tạo và chỉnh sửa bài thuyết trình, hỗ trợ trích xuất văn bản, bố cục mẫu, ghi chú và chú thích cũng như gộp/tách.'
      }
    ]
  }
]

const router = useRouter()

const loading = ref(false)
const importing = ref(false)
const listingRemoteSkills = ref(false)
const searchQuery = ref('')

const isBatchDeleteMode = ref(false)
const selectedCardSlugs = ref([])
const togglingSkillSlugs = ref([])

const skills = ref([])
const skillPreviewVisible = ref(false)
const previewSkill = ref(null)
const skillPreviewMarkdown = ref('')
const skillPreviewLoading = ref(false)
const skillPreviewError = ref('')
const deletingPreviewSkill = ref(false)
let previewRequestSeq = 0
const installFlowOpen = ref(false)
const installFlow = ref(null)

const activeTab = ref('repo') // 'repo' hoặc 'search'

const remoteInstallForm = reactive({
  source: 'https://github.com/anthropics/skills',
  skills: []
})
const remoteSkillOptions = ref([])
const repoFilterKeyword = ref('')
const selectedRepoSkills = ref([])
const hasSingleRepoSkill = computed(() => remoteSkillOptions.value.length === 1)
const singleRepoSkill = computed(() => remoteSkillOptions.value[0] || null)

const searchKeyword = ref('')
const searchingRemoteSkills = ref(false)
const searchedSkills = ref([])
const selectedSearchSkills = ref([])
const hasSingleSearchedSkill = computed(() => searchedSkills.value.length === 1)
const singleSearchedSkill = computed(() => searchedSkills.value[0] || null)
const remoteSelectionSummary = computed(() => {
  if (activeTab.value === 'repo') {
    if (!remoteSkillOptions.value.length) return 'Vui lòng kéo Skill từ kho lưu trữ trước'
    return `Đã chọn ${selectedRepoSkills.value.length} / Phát hiện tổng cộng ${remoteSkillOptions.value.length} Skill`
  }

  if (!searchedSkills.value.length) return 'Vui lòng nhập từ khóa để tìm Skill'
  return `Đã chọn ${selectedSearchSkills.value.length} / Tìm thấy ${searchedSkills.value.length} Skill`
})

const repoHistory = ref([])

const matchesSearch = (skill) => {
  if (!searchQuery.value) return true
  const q = searchQuery.value.toLowerCase()
  const text = [
    skill.name,
    skill.slug,
    skill.description,
    ...(skill.skills || []).flatMap((item) => [item.name, item.slug, item.description])
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return text.includes(q)
}

const installedSkillCards = computed(() =>
  (skills.value || []).map((skill) => ({
    ...skill,
    sourceType: skill.source_type || 'upload',
    sourceScope: skill.source_scope
  }))
)

const installedPersonalSkillKeys = computed(() => {
  const keys = new Set()
  installedSkillCards.value.forEach((skill) => {
    if (skill.sourceScope !== 'personal') return
    const identifiers = [skill.slug, skill.name]
    identifiers.forEach((value) => {
      if (value) keys.add(String(value).toLowerCase())
    })
  })
  return keys
})

const recommendedSuiteCards = computed(() =>
  RECOMMENDED_SUITES.map((suite) => ({ ...suite, isSuite: true }))
)

const filteredInstalledSkills = computed(() => installedSkillCards.value.filter(matchesSearch))
const skillGroups = computed(() => [
  {
    key: 'recommended',
    title: 'Đề xuất',
    skills: isBatchDeleteMode.value ? [] : recommendedSuiteCards.value.filter(matchesSearch)
  },
  {
    key: 'personal',
    title: 'Skill cá nhân',
    skills: isBatchDeleteMode.value
      ? []
      : filteredInstalledSkills.value.filter((skill) => skill.sourceScope === 'personal')
  },
  {
    key: 'builtin',
    title: 'Tích hợp sẵn',
    skills: filteredInstalledSkills.value.filter((skill) => skill.sourceType === 'builtin')
  },
  {
    key: 'uploaded',
    title: 'Dùng chung',
    skills: filteredInstalledSkills.value.filter(
      (skill) => skill.sourceType !== 'builtin' && skill.sourceScope !== 'personal'
    )
  }
])
const visibleSkillGroups = computed(() => skillGroups.value.filter((group) => group.skills.length))
const filteredDeletableSkills = computed(() =>
  filteredInstalledSkills.value.filter(
    (skill) =>
      canManageSkill(skill) && skill.sourceType !== 'builtin' && skill.sourceScope !== 'personal'
  )
)
const canDeletePreviewSkill = computed(
  () =>
    !!previewSkill.value &&
    canManageSkill(previewSkill.value) &&
    previewSkill.value.sourceType !== 'builtin'
)

// Lọc danh sách kỹ năng được trích xuất từ kho lưu trữ
const filteredRepoSkills = computed(() => {
  if (!repoFilterKeyword.value.trim()) return remoteSkillOptions.value
  const kw = repoFilterKeyword.value.trim().toLowerCase()
  return remoteSkillOptions.value.filter(
    (item) =>
      item.name.toLowerCase().includes(kw) ||
      (item.description && item.description.toLowerCase().includes(kw))
  )
})

// Quản lý Chọn hàng loạt/Bỏ chọn/Xóa sạch
const handleRepoSelectAll = () => {
  selectedRepoSkills.value = filteredRepoSkills.value.map((item) => item.name)
}
const handleRepoSelectNone = () => {
  selectedRepoSkills.value = []
}
const handleRepoSelectInvert = () => {
  const currentSelected = new Set(selectedRepoSkills.value)
  const newSelected = []
  filteredRepoSkills.value.forEach((item) => {
    if (!currentSelected.has(item.name)) {
      newSelected.push(item.name)
    }
  })
  selectedRepoSkills.value = newSelected
}

const handleSearchSelectAll = () => {
  selectedSearchSkills.value = [...searchedSkills.value]
}
const handleSearchSelectNone = () => {
  selectedSearchSkills.value = []
}
const handleSearchSelectInvert = () => {
  const newSelected = []
  searchedSkills.value.forEach((item) => {
    const isSelected = selectedSearchSkills.value.some(
      (s) => s.name === item.name && s.source === item.source
    )
    if (!isSelected) {
      newSelected.push(item)
    }
  })
  selectedSearchSkills.value = newSelected
}

const handleToggleRepoSkill = (name, checked) => {
  if (checked) {
    if (!selectedRepoSkills.value.includes(name)) {
      selectedRepoSkills.value.push(name)
    }
  } else {
    selectedRepoSkills.value = selectedRepoSkills.value.filter((n) => n !== name)
  }
}

const toggleRepoSkillFromRow = (name) => {
  handleToggleRepoSkill(name, !selectedRepoSkills.value.includes(name))
}

const isSearchSkillSelected = (item) =>
  selectedSearchSkills.value.some(
    (skill) => skill.name === item.name && skill.source === item.source
  )

const handleToggleSearchSkill = (item, checked) => {
  if (checked) {
    const isExist = selectedSearchSkills.value.some(
      (s) => s.name === item.name && s.source === item.source
    )
    if (!isExist) {
      selectedSearchSkills.value.push(item)
    }
  } else {
    selectedSearchSkills.value = selectedSearchSkills.value.filter(
      (s) => !(s.name === item.name && s.source === item.source)
    )
  }
}

const toggleSearchSkillFromRow = (item) => {
  handleToggleSearchSkill(item, !isSearchSkillSelected(item))
}

const sourceTypeLabel = (sourceType) => {
  if (sourceType === 'personal') return 'Skill cá nhân'
  if (sourceType === 'builtin') return 'Tích hợp sẵn'
  if (sourceType === 'remote') return 'Từ xa'
  return 'Tải lên'
}

/** Trả về nhãn ngắn gọn của phạm vi chia sẻ Skill. */
const getSkillShareLabel = (skill) => getShareConfigLabel(skill?.share_config)

const skillCardTags = (skill) => {
  if (skill.sourceScope === 'personal') {
    return [
      { name: 'Skill cá nhân', color: 'gray' },
      ...(skill.overrides_shared ? [{ name: 'Đang ghi đè phiên bản dùng chung', color: 'orange' }] : [])
    ]
  }
  return [
    { name: getSkillShareLabel(skill), color: 'gray' },
    ...(skill.shadowed_by_personal ? [{ name: 'Đã bị phiên bản cá nhân ghi đè', color: 'orange' }] : [])
  ]
}

const canManageSkill = (skill) => skill?.can_manage !== false
const isSkillToggling = (slug) => togglingSkillSlugs.value.includes(slug)
const navigateToDetail = (skill) => {
  if (skill?.sourceScope === 'personal') return
  router.push({ path: `/extensions/skill/${encodeURIComponent(skill.slug)}` })
}

const closeSkillPreview = () => {
  skillPreviewVisible.value = false
}

const openSkillPreview = async (skill) => {
  if (!skill?.slug) return
  const requestSeq = ++previewRequestSeq
  previewSkill.value = skill
  skillPreviewMarkdown.value = ''
  skillPreviewError.value = ''
  skillPreviewLoading.value = true
  skillPreviewVisible.value = true
  try {
    const result =
      skill.sourceScope === 'personal'
        ? await skillApi.getPersonalSkillFile(skill.slug, 'SKILL.md')
        : await skillApi.getSkillFile(skill.slug, 'SKILL.md')
    if (requestSeq !== previewRequestSeq || previewSkill.value?.slug !== skill.slug) return
    skillPreviewMarkdown.value = result?.data?.content || ''
  } catch (error) {
    if (requestSeq !== previewRequestSeq || previewSkill.value?.slug !== skill.slug) return
    skillPreviewError.value =
      error?.response?.data?.detail || error.message || 'Đọc SKILL.md thất bại'
  } finally {
    if (requestSeq === previewRequestSeq) skillPreviewLoading.value = false
  }
}

const goToPreviewSkillManagement = () => {
  if (!previewSkill.value) return
  navigateToDetail(previewSkill.value)
  closeSkillPreview()
}

const handleCardClick = (skill) => {
  if (isBatchDeleteMode.value) {
    handleToggleCardSelect(skill.slug)
  } else {
    openSkillPreview(skill)
  }
}

const handleToggleCardSelect = (slug) => {
  const target = installedSkillCards.value.find(
    (skill) => skill.slug === slug && skill.sourceScope !== 'personal'
  )
  if (!canManageSkill(target) || target?.sourceType === 'builtin') return
  const idx = selectedCardSlugs.value.indexOf(slug)
  if (idx > -1) {
    selectedCardSlugs.value.splice(idx, 1)
  } else {
    selectedCardSlugs.value.push(slug)
  }
}

const handleToggleSkillEnabled = async (skill) => {
  if (!skill || !canManageSkill(skill) || isSkillToggling(skill.slug)) return
  const enabled = skill.enabled === false
  togglingSkillSlugs.value.push(skill.slug)
  try {
    const result = await skillApi.updateSkillEnabled(skill.slug, enabled)
    const updatedSkill = result?.data
    const index = skills.value.findIndex(
      (item) => item.slug === skill.slug && item.source_scope !== 'personal'
    )
    if (updatedSkill && index > -1) {
      skills.value[index] = updatedSkill
    } else {
      await fetchSkills()
    }
    if (previewSkill.value?.slug === skill.slug) {
      previewSkill.value = updatedSkill
        ? { ...updatedSkill, sourceType: updatedSkill.source_type || 'upload' }
        : { ...previewSkill.value, enabled }
    }
    message.success(`Skill đã được ${enabled ? 'bật' : 'tắt'}`)
  } catch (error) {
    message.error(
      error?.response?.data?.detail || error.message || 'Cập nhật trạng thái Skill thất bại'
    )
  } finally {
    togglingSkillSlugs.value = togglingSkillSlugs.value.filter((slug) => slug !== skill.slug)
  }
}

const handlePreviewToggle = () => {
  if (!previewSkill.value) return
  handleToggleSkillEnabled(previewSkill.value)
}

const confirmDeletePreviewSkill = () => {
  const target = previewSkill.value
  if (!target || !canDeletePreviewSkill.value || deletingPreviewSkill.value) return

  Modal.confirm({
    title: `Gỡ cài đặt ${target.name || target.slug}`,
    content:
      target.sourceScope === 'personal'
        ? 'Sau khi gỡ cài đặt sẽ xóa Skill khỏi không gian làm việc cá nhân; nếu có phiên bản dùng chung cùng tên, Agent sẽ quay lại dùng phiên bản dùng chung.'
        : 'Sau khi gỡ cài đặt sẽ xóa bản ghi cơ sở dữ liệu và tệp cục bộ, thao tác không thể khôi phục.',
    okText: 'Gỡ cài đặt',
    okType: 'danger',
    cancelText: 'Hủy',
    async onOk() {
      deletingPreviewSkill.value = true
      try {
        if (target.sourceScope === 'personal') {
          await skillApi.deletePersonalSkill(target.slug)
        } else {
          await skillApi.deleteSkill(target.slug)
        }
        message.success('Skill đã được gỡ cài đặt')
        closeSkillPreview()
        previewSkill.value = null
        await fetchSkills()
      } catch (error) {
        message.error(error?.response?.data?.detail || error.message || 'Gỡ cài đặt Skill thất bại')
      } finally {
        deletingPreviewSkill.value = false
      }
    }
  })
}

const handleBatchSelectAll = () => {
  selectedCardSlugs.value = filteredDeletableSkills.value.map((skill) => skill.slug)
}

const handleBatchSelectNone = () => {
  selectedCardSlugs.value = []
}

const handleBatchSelectInvert = () => {
  const currentSet = new Set(selectedCardSlugs.value)
  selectedCardSlugs.value = filteredDeletableSkills.value
    .filter((skill) => !currentSet.has(skill.slug))
    .map((skill) => skill.slug)
}

const exitBatchDeleteMode = () => {
  isBatchDeleteMode.value = false
  selectedCardSlugs.value = []
}

const handleBatchDelete = () => {
  const deletableSlugs = selectedCardSlugs.value.filter((slug) => {
    const target = installedSkillCards.value.find(
      (skill) => skill.slug === slug && skill.sourceScope !== 'personal'
    )
    return (
      canManageSkill(target) &&
      target?.sourceType !== 'builtin' &&
      target?.sourceScope !== 'personal'
    )
  })
  if (deletableSlugs.length === 0) return

  Modal.confirm({
    title: 'Bạn có chắc chắn muốn xóa hàng loạt các kỹ năng đã chọn không?',
    content: `Bạn đã chọn ${deletableSlugs.length} kỹ năng. Thao tác này sẽ xóa vĩnh viễn khỏi CSDL và ổ đĩa, không thể khôi phục!`,
    okText: 'Xác nhận xóa',
    okType: 'danger',
    cancelText: 'Hủy',
    onOk: async () => {
      loading.value = true
      try {
        const res = await skillApi.deleteSkillsBatch(deletableSlugs)
        const results = res?.data || []
        const successList = results.filter((r) => r.success)
        const failList = results.filter((r) => !r.success)

        if (failList.length === 0) {
          message.success(`Xóa hàng loạt thành công, đã xóa ${successList.length} kỹ năng`)
        } else {
          message.warning(
            `Hoàn tất xóa hàng loạt: Thành công ${successList.length}, Thất bại ${failList.length}`
          )
        }

        exitBatchDeleteMode()
        await fetchSkills()
      } catch (error) {
        message.error(error?.response?.data?.detail || error.message || 'Xóa hàng loạt thất bại')
      } finally {
        loading.value = false
      }
    }
  })
}

const fetchSkills = async ({ refreshPersonal = false } = {}) => {
  loading.value = true
  try {
    const skillResult = await skillApi.listSkillCards({ refreshPersonal })
    skills.value = skillResult?.data || []
  } catch {
    message.error('Tải thất bại')
  } finally {
    loading.value = false
  }
}

const beforeSkillUpload = (file) => {
  const lower = file.name.toLowerCase()
  if (!lower.endsWith('.zip') && lower !== 'skill.md') {
    message.error('Chỉ hỗ trợ tải lên tệp .zip hoặc SKILL.md')
    return false
  }
  return true
}

const openInstallFlow = (flow) => {
  installFlow.value = flow
  installFlowOpen.value = true
}

const resetRemoteSelection = () => {
  selectedRepoSkills.value = []
  selectedSearchSkills.value = []
  remoteSkillOptions.value = []
  searchedSkills.value = []
  repoFilterKeyword.value = ''
  searchKeyword.value = ''
}

const closeInstallFlow = () => {
  const wasRemoteFlow = installFlow.value?.kind === 'remote'
  installFlowOpen.value = false
  installFlow.value = null
  if (wasRemoteFlow) resetRemoteSelection()
}

const openRecommendedSuite = (suite) => {
  openInstallFlow({
    kind: 'suite',
    suite,
    installedSlugs: [...installedPersonalSkillKeys.value]
  })
}

const handleInstallFlowCompleted = async ({ success, failed }) => {
  if (failed === 0) message.success(`Đã thêm ${success} Skill`)
  else message.warning(`Cài đặt hoàn tất: Thành công ${success}, Thất bại ${failed}`)
  await fetchSkills()
}

const handleImportUpload = async ({ file, onSuccess, onError }) => {
  importing.value = true
  try {
    const result = await skillApi.prepareSkillUpload(file)
    openInstallFlow({
      kind: 'draft',
      title: `Cài đặt ${file.name}`,
      description: 'Kiểm tra phụ thuộc và phạm vi hiệu lực của Skill, sau đó hoàn tất cài đặt.',
      drafts: [result?.data]
    })
    onSuccess?.(result)
  } catch (e) {
    message.error(e?.response?.data?.detail || e.message || 'Phân tích Skill thất bại')
    onError?.(e)
  } finally {
    importing.value = false
  }
}

const handleOpenRemoteInstall = () => {
  resetRemoteSelection()
  openInstallFlow({
    kind: 'remote',
    title: 'Cài đặt Skill từ xa',
    description: 'Kéo theo kho lưu trữ hoặc tìm kiếm toàn cục, chọn Skill cần cài đặt.'
  })
}

const rememberRemoteSource = (source) => {
  let history = [...repoHistory.value]
  history = history.filter((item) => item !== source)
  history.unshift(source)
  if (history.length > 10) {
    history = history.slice(0, 10)
  }
  repoHistory.value = history
  localStorage.setItem('yuxi_remote_repo_history', JSON.stringify(history))
}

const handleListRemoteSkills = async () => {
  const source = remoteInstallForm.source.trim()
  if (!source) {
    message.warning('Vui lòng nhập kho lưu trữ nguồn')
    return
  }
  listingRemoteSkills.value = true
  try {
    const result = await skillApi.listRemoteSkills(source)
    remoteSkillOptions.value = result?.data || []
    selectedRepoSkills.value =
      remoteSkillOptions.value.length === 1 ? [remoteSkillOptions.value[0].name] : []
    if (!remoteSkillOptions.value.length) {
      message.warning('Không tìm thấy Skills có thể cài đặt')
      return
    }
    if (remoteSkillOptions.value.length === 1) {
      message.success('Đã tìm thấy 1 Skill, tự động chọn')
    } else {
      message.success(`Đã tìm thấy ${remoteSkillOptions.value.length}  Skills`)
    }

    rememberRemoteSource(source)
  } catch (error) {
    message.error(error?.response?.data?.detail || error.message || 'Lấy Skills từ xa thất bại')
  } finally {
    listingRemoteSkills.value = false
  }
}

const loadHistory = () => {
  try {
    const raw = localStorage.getItem('yuxi_remote_repo_history')
    if (raw) {
      repoHistory.value = JSON.parse(raw)
    }
  } catch (e) {
    console.error('Failed to load repo history', e)
  }
}

const deleteHistoryItem = (item) => {
  repoHistory.value = repoHistory.value.filter((h) => h !== item)
  localStorage.setItem('yuxi_remote_repo_history', JSON.stringify(repoHistory.value))
}

const clearAllHistory = () => {
  repoHistory.value = []
  localStorage.removeItem('yuxi_remote_repo_history')
  message.success('Lịch sử đã được xóa')
}

const handleSelectHistory = ({ key }) => {
  if (key === 'clear-all-history') {
    clearAllHistory()
    return
  }
  remoteInstallForm.source = key
}

const handleSearchRemoteSkills = async () => {
  const query = searchKeyword.value.trim()
  if (!query) {
    message.warning('Vui lòng nhập từ khóa tìm kiếm')
    return
  }
  searchingRemoteSkills.value = true
  try {
    const result = await skillApi.searchRemoteSkills(query)
    searchedSkills.value = result?.data || []
    selectedSearchSkills.value = searchedSkills.value.length === 1 ? [...searchedSkills.value] : []
    if (!searchedSkills.value.length) {
      message.warning('Không tìm thấy Skills liên quan')
    } else if (searchedSkills.value.length === 1) {
      message.success('Tìm thấy 1 Skill, tự động chọn')
    } else {
      message.success(`Tìm thấy ${searchedSkills.value.length}  Skills`)
    }
  } catch (error) {
    message.error(
      error?.response?.data?.detail || error.message || 'Tìm kiếm Skills từ xa thất bại'
    )
  } finally {
    searchingRemoteSkills.value = false
  }
}

const startInstallRemoteSkills = () => {
  const requests = []
  if (activeTab.value === 'repo') {
    requests.push({
      source: remoteInstallForm.source.trim(),
      skills: [...selectedRepoSkills.value],
      skillDetails: remoteSkillOptions.value
        .filter((item) => selectedRepoSkills.value.includes(item.name))
        .map((item) => ({ ...item, slug: item.name }))
    })
  } else {
    const groups = new Map()
    selectedSearchSkills.value.forEach((item) => {
      if (!groups.has(item.source)) groups.set(item.source, [])
      groups.get(item.source).push(item)
    })
    groups.forEach((items, source) => {
      requests.push({
        source,
        skills: items.map((item) => item.name),
        skillDetails: items.map((item) => ({ ...item, slug: item.name }))
      })
    })
  }

  openInstallFlow({
    kind: 'remote',
    title: 'Cài đặt Skill từ xa',
    description: `${requests.length} nguồn · ${requests.reduce((total, item) => total + item.skills.length, 0)} Skill`,
    requests
  })
}

watch(activeTab, () => {
  selectedRepoSkills.value = []
  selectedSearchSkills.value = []
})

onMounted(() => {
  fetchSkills()
  loadHistory()
})

defineExpose({
  fetchSkills,
  handleImportUpload,
  openRemoteInstallModal: handleOpenRemoteInstall,
  loading
})
</script>

<style lang="less" scoped>
@import '@/assets/css/extensions.less';
</style>

<style lang="less" scoped>
.skill-empty-state {
  width: 100%;
  min-height: 280px;
  padding: 40px var(--page-padding);
}

.skill-empty-card {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 220px;
  flex-direction: column;
  border: 1px dashed var(--gray-150);
  border-radius: 16px;
  background: linear-gradient(180deg, var(--gray-0) 0%, var(--gray-25) 100%);
  color: var(--gray-500);
  text-align: center;
}

.skill-empty-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  margin-bottom: 12px;
  border-radius: 14px;
  background: var(--gray-50);
  color: var(--gray-600);
}

.skill-empty-title {
  color: var(--gray-800);
  font-size: 15px;
  font-weight: 700;
  line-height: 22px;
}

.skill-empty-desc {
  margin-top: 4px;
  color: var(--gray-500);
  font-size: 13px;
  line-height: 20px;
}

.card-wrapper {
  position: relative;

  :deep(.info-card-mini-desc) {
    display: -webkit-box;
    min-height: 36px;
    color: var(--gray-700);
    white-space: normal;
    line-clamp: 2;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }

  :deep(.info-card-mini .info-card-icon) {
    align-self: flex-start;
  }

  &.batch-mode {
    :deep(.info-card) {
      cursor: pointer;
      border-color: var(--gray-200);

      &:hover {
        border-color: var(--gray-300);
      }
    }

    :deep(.info-card-status),
    :deep(.info-card-mini-action) {
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.2s ease;
    }

    :deep(.info-card-mini .info-card-info) {
      padding-right: 28px;
    }
  }

  &.selected {
    :deep(.info-card) {
      border-color: var(--gray-500) !important;
      background: var(--gray-25) !important;
    }
  }

  .card-select-checkbox {
    position: absolute;
    top: 16px;
    right: 16px;
    z-index: 10;
  }
}

.skill-enabled-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  background: var(--gray-0);
  color: var(--gray-600);
  font-size: 18px;
  font-weight: 600;
  line-height: 1;
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    background-color 0.18s ease,
    color 0.18s ease;

  &:hover,
  &:focus {
    outline: none;
    border-color: var(--gray-300);
    background: var(--gray-50);
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.45;
  }

  &.loading:disabled {
    cursor: wait;
    opacity: 1;
  }

  &.enabled {
    color: var(--color-success-700);

    .action-icon-minus {
      display: none;
    }

    &:hover,
    &:focus {
      border-color: var(--color-error-200, #ffccc7);
      background: var(--color-error-50, #fff2f0);
      color: var(--color-error-700, #cf1322);

      .action-icon-check {
        display: none;
      }

      .action-icon-minus {
        display: block;
      }
    }
  }
}

.action-icon {
  flex-shrink: 0;
}

.skill-preview-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.skill-preview-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.skill-preview-title-area {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 10px;
}

.skill-preview-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 9px;
  background: var(--gray-50);
  color: var(--gray-600);
}

.skill-preview-title-text {
  min-width: 0;
}

.skill-preview-title {
  overflow: hidden;
  color: var(--gray-900);
  font-size: 16px;
  font-weight: 700;
  line-height: 22px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.skill-preview-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 2px;
  color: var(--gray-500);
  font-size: 12px;
  line-height: 18px;
}

.skill-preview-disabled-tag {
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 6px;
  border-radius: 999px;
  background: var(--gray-100);
  color: var(--gray-600);
  font-size: 11px;
  font-weight: 600;
}

.skill-preview-actions {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  gap: 8px;
  padding-top: 2px;
}

.skill-preview-body {
  min-height: 260px;
  max-height: min(56vh, 520px);
  padding: 14px 16px;
  overflow-y: auto;
  border: 1px solid var(--gray-150);
  border-radius: 12px;
  background: var(--gray-25);

  :deep(.yk-markdown-preview) {
    background: transparent;
  }
}

.skill-preview-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 220px;
}

.skill-preview-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
}

.skill-preview-footer-left,
.skill-preview-footer-right {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.remote-install-panel {
  :deep(.install-tabs > .ant-tabs-nav .ant-tabs-nav-wrap) {
    justify-content: center;
  }

  .repo-input-row {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-bottom: 4px;

    .repo-input-field {
      flex: 1;
      min-width: 0;
    }
  }

  .history-trigger-wrapper {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    cursor: pointer;
    outline: none;
    margin-right: -4px;
    border-radius: 4px;
    transition: background-color 0.2s ease;

    &:hover {
      background-color: var(--gray-100);
    }

    &:focus,
    &:focus-visible {
      outline: none;
    }
  }

  .history-icon-trigger {
    color: var(--gray-400);
    transition: color 0.2s ease;
    outline: none;

    &:hover {
      color: var(--gray-700);
    }

    &.has-history {
      color: var(--gray-500);

      &:hover {
        color: var(--gray-700);
      }
    }
  }

  .repo-hint-text {
    font-size: 12px;
    color: var(--gray-400);
    margin-bottom: 12px;
    line-height: 1.4;

    a {
      color: var(--gray-700);
      text-decoration: underline;
    }
  }

  .tab-content-wrapper {
    padding: 4px 0 8px 0;
  }

  .skills-list-section {
    margin-top: 12px;
    border: 1px solid var(--gray-150);
    border-radius: 8px;
    overflow: hidden;
    background: var(--gray-0);
  }

  .list-operations-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid var(--gray-150);
    padding: 8px 10px;

    .op-buttons {
      display: flex;
      gap: 2px;

      .ant-btn {
        padding: 0 4px;
        height: auto;
        font-size: 12px;
        color: var(--gray-600);

        &:hover {
          color: var(--gray-900);
        }
      }
    }
  }

  .skills-list-viewport {
    max-height: min(42vh, 420px);
    overflow-y: auto;
    overscroll-behavior: contain;
    background: var(--gray-0);
  }

  .remote-skills-list-container {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 1px;
    background: var(--gray-100);
  }

  .remote-skill-row {
    display: flex;
    align-items: center;
    min-height: 46px;
    padding: 6px 10px;
    gap: 8px;
    background: var(--gray-0);
    cursor: pointer;
    transition: background-color 0.18s ease;

    &:hover,
    &.selected {
      background: var(--gray-25);
    }

    &:focus-visible {
      outline: 2px solid var(--gray-400);
      outline-offset: -2px;
    }

    &[aria-disabled='true'] {
      cursor: not-allowed;
    }
  }

  .remote-row-checkbox {
    pointer-events: none;
  }

  .single-remote-skill-card {
    border: 1px solid var(--gray-150);
    border-radius: 6px;
    background: var(--gray-0);
    padding: 12px;
  }

  .single-remote-skill-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    min-width: 0;

    .ant-tag {
      flex-shrink: 0;
      margin-inline-end: 0;
    }
  }

  .single-remote-skill-name {
    line-height: 20px;
    font-weight: 600;
    color: var(--gray-900);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .single-remote-skill-meta {
    margin-top: 2px;
    font-size: 12px;
    line-height: 18px;
    color: var(--gray-500);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .remote-skill-row-content {
    display: flex;
    min-width: 0;
    flex: 1;
    flex-direction: column;

    .skill-item-name {
      font-weight: 600;
      color: var(--gray-900);
    }

    .skill-item-desc {
      display: block;
      font-size: 12px;
      color: var(--gray-500);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
  }

  .skill-install-count {
    flex-shrink: 0;
    color: var(--gray-500);
    font-size: 11px;
  }
}

@media (max-width: 600px) {
  .remote-install-panel {
    .skills-list-viewport {
      max-height: 40vh;
      overflow-y: auto;
    }

    .remote-skills-list-container {
      grid-template-columns: 1fr;
    }
  }
}

.modal-footer-summary {
  color: var(--gray-500);
  font-size: 12px;
  line-height: 18px;
}

.modal-footer-buttons {
  display: flex;
  margin-left: auto;
  gap: 8px;
}
</style>

<!-- NOTE: unscoped style block dành cho dropdown overlay xuyên thấu teleport -->
<style lang="less">
/* Ant Design Dropdown overlay qua teleport Gắn vào body，
   scoped CSS không thể xuyên thấu, do đó phải sử dụng kiểu unscoped.
   Sử dụng .history-dropdown-menu Như là overlayClassName Không gian tên。 */
.history-dropdown-menu {
  min-width: 280px;

  .ant-dropdown-menu {
    padding: 4px;
  }

  .ant-dropdown-menu-item {
    padding: 8px 12px;
    border-radius: 6px;

    .ant-dropdown-menu-title-content {
      display: flex;
      align-items: center;
      width: 100%;
    }
  }
}

/* Dòng lịch sử: địa chỉ kho + nút xóa */
.history-item-menu-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  gap: 12px;

  .history-item-text {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 13px;
    color: var(--gray-800);
    line-height: 1;
  }

  .history-item-del-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    color: var(--gray-400);
    cursor: pointer;
    border-radius: 4px;
    transition: all 0.2s ease;
    flex-shrink: 0;

    svg {
      display: block;
    }

    &:hover {
      color: var(--color-error-500, #ff4d4f);
      background: var(--color-error-10, rgba(255, 77, 79, 0.1));
    }
  }
}

.history-empty-text {
  color: var(--gray-400);
  font-size: 12px;
}

/* Nội dung nút Xóa lịch sử — Biểu tượng bên trái chữ bên phải, căn giữa ngang */
.clear-history-btn-content {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--color-error-500, #ff4d4f);
  font-weight: 500;
  font-size: 13px;
  width: 100%;

  .clear-icon {
    display: flex;
    align-items: center;
  }
}
</style>
