<template>
  <a-modal
    :open="open"
    class="skill-install-flow-modal"
    :width="840"
    :closable="canClose"
    :mask-closable="canClose"
    :keyboard="canClose"
    :footer="null"
    :destroy-on-close="true"
    @cancel="handleClose"
  >
    <div class="install-flow-shell">
      <header class="install-flow-header">
        <div class="install-flow-icon"><PackageOpen :size="19" /></div>
        <div>
          <h2>{{ modalTitle }}</h2>
          <p>{{ modalDescription }}</p>
        </div>
      </header>

      <ol class="install-flow-steps" aria-label="Installation Progress">
        <li
          v-for="(label, index) in stepLabels"
          :key="label"
          :class="{ active: currentStep === index, completed: currentStep > index }"
          :aria-current="currentStep === index ? 'step' : undefined"
        >
          <span class="step-dot">{{ currentStep > index ? '✓' : index + 1 }}</span>
          <span class="step-label">{{ label }}</span>
        </li>
      </ol>

      <main
        class="install-flow-body"
        :class="{ 'remote-selection-body': phase === 'selecting' && flow?.kind === 'remote' }"
      >
        <section v-if="phase === 'selecting'" class="flow-section">
          <slot v-if="flow?.kind === 'remote'" name="selection" />
          <template v-else>
            <div class="selection-toolbar">
              <span>Select skills to load</span>
              <div>
                <a-button type="link" size="small" @click="selectAllAvailable">Select all</a-button>
                <a-button type="link" size="small" @click="selectedSlugs = []">Clear</a-button>
              </div>
            </div>
            <div class="flow-item-list selection-list">
              <label
                v-for="skill in suiteSkills"
                :key="skill.slug"
                class="selection-item"
                :class="{ installed: isInstalled(skill.slug) }"
              >
                <a-checkbox
                  :checked="selectedSlugs.includes(skill.slug)"
                  :disabled="isInstalled(skill.slug)"
                  @change="(event) => toggleSelection(skill.slug, event.target.checked)"
                />
                <span class="flow-item-content">
                  <strong>{{ skill.name }}</strong>
                  <small>{{ skill.description || skill.slug }}</small>
                </span>
                <span v-if="isInstalled(skill.slug)" class="status-badge neutral">Installed</span>
              </label>
            </div>
          </template>
        </section>

        <section v-else-if="phase === 'preparing'" class="flow-section" aria-live="polite">
          <div class="flow-loading-state" :class="{ failed: flowError }">
            <div class="loading-state-icon">
              <XCircle v-if="flowError" :size="20" />
              <LoaderCircle v-else :size="20" class="spin" />
            </div>
            <strong>
              {{ flowError ? 'Failed to load skills' : `Loading ${progressItems.length} skills` }}
            </strong>
            <span>
              {{ flowError || `Fetching and parsing from ${loadingSourceCount} source(s), usually takes a moment` }}
            </span>
          </div>
        </section>

        <section v-else-if="phase === 'reviewing'" class="flow-section">
          <div class="review-heading">
            <strong>Confirm Installation</strong>
            <span>{{ readyItems.length }} skills sharing settings below</span>
          </div>
          <div class="review-list">
            <div
              v-for="item in reviewItems"
              :key="`${item.draft_id}:${item.slug}`"
              class="review-item"
              :class="{ failed: item.success === false }"
            >
              <span class="review-title">
                <strong>{{ item.name || item.slug }}</strong>
                <small>{{ item.description || item.error || 'No description' }}</small>
              </span>
              <span v-if="item.success === false" class="status-badge error">Failed to parse</span>
              <button
                type="button"
                class="review-remove-button"
                :aria-label="`Remove ${item.name || item.slug}`"
                @click="removeReviewItem(item)"
              >
                <XIcon :size="15" />
              </button>
              <div
                v-if="installTarget === 'shared' && item.warnings?.length"
                class="review-warning"
                role="alert"
              >
                {{ item.warnings.join('; ') }}
              </div>
            </div>
          </div>
          <div class="install-target-section">
            <h3>Installation Target</h3>
            <div class="install-target-options">
              <button
                type="button"
                class="install-target-option"
                :class="{ selected: installTarget === 'personal' }"
                :aria-pressed="installTarget === 'personal'"
                @click="installTarget = 'personal'"
              >
                <span class="install-target-title">Personal Workspace <b>Recommended</b></span>
                <span>Only available to you, stored in personal workspace, not saved to platform database.</span>
              </button>
              <button
                v-if="userStore.isAdmin"
                type="button"
                class="install-target-option"
                :class="{ selected: installTarget === 'shared' }"
                :aria-pressed="installTarget === 'shared'"
                @click="installTarget = 'shared'"
              >
                <span class="install-target-title">Shared Skill</span>
                <span>Saved to platform skill library with customizable scope (users, departments, or global).</span>
              </button>
            </div>
            <div v-if="installTarget === 'personal'" class="personal-install-note">
              Personal skills do not load tool, MCP, or other skill dependencies; identical slug will override the shared version.
            </div>
          </div>
          <div v-if="installTarget === 'shared'" class="share-config-section">
            <h3>Effective Scope</h3>
            <ShareConfigForm
              ref="shareConfigFormRef"
              v-model="shareConfig"
              :auto-select-user-dept="true"
              :allowed-access-levels="allowedAccessLevels"
            />
          </div>
        </section>

        <section v-else-if="phase === 'installing'" class="flow-section" aria-live="polite">
          <div class="flow-loading-state">
            <div class="loading-state-icon">
              <LoaderCircle :size="20" class="spin" />
            </div>
            <strong>Installing {{ installItems.length }} skills</strong>
            <span>Installing to: {{ installTargetLabel }}</span>
          </div>
        </section>

        <section v-else class="flow-section" aria-live="polite">
          <div class="result-heading">
            <strong>{{ resultTitle }}</strong>
            <span
              >{{ successfulInstallCount }} succeeded, {{ failedInstallItems.length }} failed</span
            >
          </div>
          <StatusItemList :items="installItems" />
          <div v-if="flowError" class="flow-alert" role="alert">{{ flowError }}</div>
        </section>
      </main>

      <footer class="install-flow-footer">
        <slot v-if="phase === 'selecting' && flow?.kind === 'remote'" name="selection-footer" />
        <template v-else>
          <span class="footer-summary">{{ footerSummary }}</span>
          <div class="footer-actions">
            <template v-if="phase === 'selecting'">
              <a-button @click="handleClose">Cancel</a-button>
              <a-button type="primary" :disabled="selectedSlugs.length === 0" @click="prepareSuite">
                Load Selected Skills
              </a-button>
            </template>
            <template v-else-if="phase === 'preparing'">
              <a-button v-if="flowError" @click="handleClose">Close</a-button>
              <a-button v-else loading disabled>Loading</a-button>
            </template>
            <template v-else-if="phase === 'reviewing'">
              <a-button @click="handleClose">Cancel</a-button>
              <a-button type="primary" :disabled="readyItems.length === 0" @click="installDrafts">
                Install {{ readyItems.length }} Skills · {{ installTargetLabel }}
              </a-button>
            </template>
            <template v-else-if="phase === 'installing'">
              <a-button type="primary" loading disabled>Installing</a-button>
            </template>
            <template v-else>
              <a-button v-if="failedInstallItems.length" @click="retryFailedItems">
                Retry Failed Items
              </a-button>
              <a-button type="primary" @click="finishFlow">Done</a-button>
            </template>
          </div>
        </template>
      </footer>
    </div>
  </a-modal>
</template>

<script setup>
import { computed, defineComponent, h, nextTick, ref, watch } from 'vue'
import {
  CheckCircle2,
  Circle,
  LoaderCircle,
  PackageOpen,
  X as XIcon,
  XCircle
} from 'lucide-vue-next'
import ShareConfigForm from '@/components/ShareConfigForm.vue'
import { skillApi } from '@/apis/skill_api'
import { useUserStore } from '@/stores/user'

const props = defineProps({
  open: { type: Boolean, default: false },
  flow: { type: Object, default: null }
})

const emit = defineEmits(['close', 'completed'])
const userStore = useUserStore()

const stepLabels = ['Select', 'Load', 'Target', 'Done']
const phase = ref('selecting')
const selectedSlugs = ref([])
const progressItems = ref([])
const drafts = ref([])
const reviewItems = ref([])
const installItems = ref([])
const shareConfig = ref({
  version: 2,
  read_scope: { access_level: 'user', department_ids: [], user_uids: [] },
  manage_scope: null
})
const installTarget = ref('personal')
const allowedAccessLevels = ref(['user'])
const flowError = ref('')
const shareConfigFormRef = ref(null)

const StatusItemList = defineComponent({
  props: { items: { type: Array, default: () => [] } },
  setup(listProps) {
    const iconFor = (status) => {
      if (status === 'success') return CheckCircle2
      if (status === 'failed') return XCircle
      if (status === 'active') return LoaderCircle
      return Circle
    }
    const labelFor = (status) =>
      ({ waiting: 'Waiting', active: 'Processing', success: 'Done', failed: 'Failed' })[status] || status
    return () =>
      h(
        'div',
        { class: 'flow-item-list status-list' },
        listProps.items.map((item) =>
          h(
            'div',
            { class: ['status-item', item.status], key: `${item.source || ''}:${item.slug}` },
            [
              h(iconFor(item.status), { size: 17, class: item.status === 'active' ? 'spin' : '' }),
              h('span', { class: 'flow-item-content' }, [
                h('strong', item.name || item.slug),
                h('small', item.error || item.description || item.slug)
              ]),
              h('span', { class: ['status-badge', item.status] }, labelFor(item.status))
            ]
          )
        )
      )
  }
})

const suiteSkills = computed(() => props.flow?.suite?.skills || [])
const installedSet = computed(
  () => new Set((props.flow?.installedSlugs || []).map((slug) => String(slug).toLowerCase()))
)
const currentStep = computed(
  () => ({ selecting: 0, preparing: 1, reviewing: 2, installing: 3, result: 3 })[phase.value]
)
const canClose = computed(
  () => phase.value !== 'installing' && (phase.value !== 'preparing' || Boolean(flowError.value))
)
const readyItems = computed(() => reviewItems.value.filter((item) => item.success !== false))
const loadingSourceCount = computed(
  () => new Set(progressItems.value.map((item) => item.source).filter(Boolean)).size
)
const shareScopeLabel = computed(() => {
  const scope = shareConfig.value.read_scope || shareConfig.value.manage_scope || shareConfig.value
  return (
    { global: 'Global', department: 'Department', user: 'Specific Users' }[scope.access_level] || 'Specific Users'
  )
})
const installTargetLabel = computed(() =>
  installTarget.value === 'personal' ? 'Personal Workspace' : shareScopeLabel.value
)
const failedInstallItems = computed(() =>
  installItems.value.filter((item) => item.status === 'failed')
)
const successfulInstallCount = computed(
  () => installItems.value.filter((item) => item.status === 'success').length
)
const resultTitle = computed(() => {
  if (!failedInstallItems.value.length) return 'All skills installed successfully'
  if (successfulInstallCount.value) return 'Partially installed'
  return 'Failed to install skills'
})
const modalTitle = computed(() =>
  props.flow?.kind === 'suite' ? `Install ${props.flow.suite.name}` : props.flow?.title || 'Install Skills'
)
const modalDescription = computed(() => {
  if (props.flow?.kind === 'suite')
    return `${props.flow.suite.provider} · ${props.flow.suite.description}`
  return props.flow?.description || 'Load skills, configure installation target and scope.'
})
const footerSummary = computed(() => {
  if (phase.value === 'selecting') return `Loading ${selectedSlugs.value.length} skills`
  if (phase.value === 'preparing')
    return flowError.value ? 'Cleaned up temporary drafts' : 'Completing load request'
  if (phase.value === 'reviewing')
    return `${readyItems.value.length} ready · ${installTargetLabel.value}`
  if (phase.value === 'installing') return 'Successful skills will not roll back if other items fail'
  return `${successfulInstallCount.value} succeeded, ${failedInstallItems.value.length} failed`
})

const cloneShareConfig = (config) => ({
  version: 2,
  read_scope:
    config?.version === 2
      ? config.read_scope
        ? {
            access_level: config.read_scope.access_level || 'user',
            department_ids: [...(config.read_scope.department_ids || [])],
            user_uids: [...(config.read_scope.user_uids || [])]
          }
        : null
      : {
          access_level: config?.access_level || 'user',
          department_ids: [...(config?.department_ids || [])],
          user_uids: [...(config?.user_uids || [])]
        },
  manage_scope:
    config?.version === 2 && config.manage_scope
      ? {
          access_level: config.manage_scope.access_level || 'global',
          department_ids: [...(config.manage_scope.department_ids || [])],
          user_uids: [...(config.manage_scope.user_uids || [])]
        }
      : null
})

const isInstalled = (slug) => installedSet.value.has(String(slug).toLowerCase())
const selectAllAvailable = () => {
  selectedSlugs.value = suiteSkills.value
    .filter((skill) => !isInstalled(skill.slug))
    .map((skill) => skill.slug)
}
const toggleSelection = (slug, checked) => {
  selectedSlugs.value = checked
    ? [...new Set([...selectedSlugs.value, slug])]
    : selectedSlugs.value.filter((item) => item !== slug)
}

const removeReviewItem = (item) => {
  reviewItems.value = reviewItems.value.filter(
    (candidate) => candidate.draft_id !== item.draft_id || candidate.slug !== item.slug
  )
}

const initializeProgressItems = (requests) => {
  progressItems.value = requests.flatMap((request) =>
    request.skills.map((slug) => ({
      slug,
      name: request.skillDetails?.find((item) => item.slug === slug)?.name || slug,
      description: request.skillDetails?.find((item) => item.slug === slug)?.description || '',
      source: request.source,
      status: 'waiting'
    }))
  )
}

const prepareRequests = async (requests) => {
  phase.value = 'preparing'
  flowError.value = ''
  drafts.value = []
  initializeProgressItems(requests)

  try {
    for (const request of requests) {
      const result = await skillApi.prepareRemoteSkills({
        source: request.source,
        skills: request.skills
      })
      if (result?.data?.draft_id) drafts.value.push(result.data)
    }
    if (!drafts.value.length) throw new Error('No installable skills found')

    openReview(drafts.value)
  } catch (error) {
    const message = error?.response?.data?.detail || error.message || 'Failed to load skills'
    await discardDrafts()
    flowError.value = message
  }
}

const openReview = (draftPayloads) => {
  drafts.value = draftPayloads.filter((draft) => draft?.draft_id)
  reviewItems.value = drafts.value.flatMap((draft) =>
    (draft.items || []).map((item) => ({
      ...item,
      source: draft.source,
      source_type: draft.source_type,
      draft_id: draft.draft_id
    }))
  )
  const first = drafts.value[0] || {}
  shareConfig.value = cloneShareConfig(first.default_share_config)
  allowedAccessLevels.value = first.allowed_access_levels || ['user']
  phase.value = 'reviewing'
}

const prepareSuite = () => {
  const details = suiteSkills.value.filter((skill) => selectedSlugs.value.includes(skill.slug))
  prepareRequests([
    { source: props.flow.suite.source, skills: selectedSlugs.value, skillDetails: details }
  ])
}

const installDrafts = async () => {
  if (installTarget.value === 'shared') {
    const validation = shareConfigFormRef.value?.validate?.()
    if (validation && !validation.valid) {
      flowError.value = validation.message || 'Please complete skill effective scope'
      return
    }
  }

  phase.value = 'installing'
  flowError.value = ''
  installItems.value = readyItems.value.map((item) => ({ ...item, status: 'waiting' }))
  try {
    for (const draft of drafts.value) {
      const slugs = readyItems.value
        .filter((item) => item.draft_id === draft.draft_id)
        .map((item) => item.slug)
      if (!slugs.length) {
        await skillApi.discardSkillInstallDraft(draft.draft_id)
        forgetDraft(draft.draft_id)
        continue
      }

      const result =
        installTarget.value === 'personal'
          ? await skillApi.confirmPersonalSkillInstallDraft(draft.draft_id, slugs)
          : await skillApi.confirmSkillInstallDraft(draft.draft_id, shareConfig.value, slugs)
      const results = result?.data || []
      applyInstallResults(results, draft.source)
      if (!results.some((item) => item.success)) {
        await skillApi.discardSkillInstallDraft(draft.draft_id)
      }
      forgetDraft(draft.draft_id)
    }
  } catch (error) {
    await discardDrafts()
    flowError.value = error?.response?.data?.detail || error.message || 'Failed to install skills'
    installItems.value
      .filter((item) => item.status === 'waiting')
      .forEach((item) => Object.assign(item, { status: 'failed', error: flowError.value }))
  } finally {
    phase.value = 'result'
  }
}

const applyInstallResults = (results, source) => {
  results.forEach((result) => {
    const item = installItems.value.find(
      (candidate) =>
        candidate.slug === (result.requested_slug || result.slug) && candidate.source === source
    )
    if (!item) return
    Object.assign(item, {
      status: result.success ? 'success' : 'failed',
      error: result.error || ''
    })
  })
}

const forgetDraft = (draftId) => {
  drafts.value = drafts.value.filter((draft) => draft.draft_id !== draftId)
}

const discardDrafts = async () => {
  const draftIds = drafts.value.map((draft) => draft.draft_id)
  drafts.value = []
  await Promise.allSettled(draftIds.map((draftId) => skillApi.discardSkillInstallDraft(draftId)))
}

const handleClose = async () => {
  if (!canClose.value) return
  if (phase.value === 'result') {
    finishFlow()
    return
  }
  if (phase.value === 'reviewing') await discardDrafts()
  emit('close')
}

const retryFailedItems = () => {
  const requestsBySource = new Map()
  failedInstallItems.value.forEach((item) => {
    if (item.source_type !== 'remote' || !item.source) return
    if (!requestsBySource.has(item.source)) requestsBySource.set(item.source, [])
    requestsBySource.get(item.source).push(item.slug)
  })
  const requests = [...requestsBySource].map(([source, skills]) => ({ source, skills }))
  if (!requests.length) {
    flowError.value = 'This failed item must be re-uploaded from the original source'
    return
  }
  prepareRequests(requests)
}

const finishFlow = () => {
  emit('completed', {
    success: successfulInstallCount.value,
    failed: failedInstallItems.value.length
  })
  emit('close')
}

watch(
  () => [props.open, props.flow],
  async ([open]) => {
    if (!open || !props.flow) return
    flowError.value = ''
    drafts.value = []
    reviewItems.value = []
    installItems.value = []
    installTarget.value = 'personal'

    if (props.flow.kind === 'suite') {
      phase.value = 'selecting'
      selectAllAvailable()
      return
    }
    if (props.flow.kind === 'remote' && !props.flow.requests?.length) {
      phase.value = 'selecting'
      return
    }
    if (props.flow.kind === 'draft') {
      openReview(props.flow.drafts || [])
      return
    }
    await nextTick()
    prepareRequests(props.flow.requests || [])
  },
  { immediate: true }
)
</script>

<style lang="less" scoped>
.install-flow-shell {
  display: flex;
  flex-direction: column;
  max-height: min(82vh, 760px);
}

.install-flow-header {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  padding-right: 28px;

  > div:last-child {
    min-width: 0;
  }

  h2 {
    margin: 0;
    color: var(--gray-900);
    font-size: 18px;
    font-weight: 650;
    line-height: 25px;
  }

  p {
    margin: 3px 0 0;
    color: var(--gray-500);
    font-size: 12px;
    line-height: 18px;
  }
}

.install-flow-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 36px;
  height: 36px;
  border-radius: 8px;
  background: var(--gray-100);
  color: var(--gray-700);
}

.install-flow-steps {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  margin: 20px 0 16px;
  padding: 0;
  list-style: none;

  li {
    position: relative;
    display: grid;
    grid-template-rows: 22px 18px;
    justify-items: center;
    gap: 4px;
    color: var(--gray-400);
    font-size: 12px;

    &::before {
      position: absolute;
      top: 11px;
      right: 50%;
      left: -50%;
      z-index: 0;
      height: 1px;
      background: var(--gray-150);
      content: '';
    }

    &:first-child::before {
      display: none;
    }

    .step-dot {
      z-index: 1;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 22px;
      height: 22px;
      border: 1px solid var(--gray-200);
      border-radius: 50%;
      background: var(--gray-0);
    }

    &.active,
    &.completed {
      color: var(--gray-800);
      font-weight: 600;

      .step-dot {
        border-color: var(--gray-500);
        background: var(--gray-50);
      }
    }

    &.completed::before {
      background: var(--gray-300);
    }
  }
}

.install-flow-body {
  min-height: 180px;
  max-height: min(52vh, 480px);
  flex: 0 1 auto;
  overflow-y: auto;
  padding: 16px;
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  background: var(--gray-25);

  &.remote-selection-body {
    min-height: 0;
    max-height: none;
    overflow: hidden;
  }
}

.flow-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.selection-toolbar,
.install-flow-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.selection-toolbar {
  color: var(--gray-700);
  font-size: 13px;
  font-weight: 600;

  :deep(.ant-btn-link) {
    color: var(--gray-600);

    &:hover {
      color: var(--gray-900);
    }
  }
}

.flow-item-list,
.review-list,
:deep(.status-list) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.selection-item,
:deep(.status-item) {
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  background: var(--gray-0);
}

.selection-list {
  overflow: hidden;
  gap: 0;
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  background: var(--gray-0);

  .selection-item {
    min-height: 60px;
    border: 0;
    border-bottom: 1px solid var(--gray-100);
    border-radius: 0;

    &:last-child {
      border-bottom: 0;
    }
  }
}

.selection-item,
:deep(.status-item) {
  display: flex;
  align-items: center;
  min-height: 54px;
  padding: 10px 12px;
  gap: 10px;
}

.selection-item {
  cursor: pointer;

  &.installed {
    color: var(--gray-400);
    cursor: not-allowed;
    background: var(--gray-50);
  }
}

.flow-item-content,
.review-title,
:deep(.status-item .flow-item-content) {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;

  strong {
    color: var(--gray-900);
    font-size: 13px;
    line-height: 20px;
  }

  small {
    overflow: hidden;
    color: var(--gray-500);
    font-size: 12px;
    line-height: 18px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

:deep(.status-item) {
  color: var(--gray-400);

  > svg {
    flex: 0 0 auto;
  }

  &.active {
    color: var(--gray-700);
  }

  &.success {
    color: var(--color-success-700);
  }

  &.failed {
    color: var(--color-error-700);
  }
}

:deep(.status-badge) {
  flex-shrink: 0;
  margin-left: auto;
  padding: 2px 7px;
  border-radius: 999px;
  background: var(--gray-100);
  color: var(--gray-600);
  font-size: 11px;
  line-height: 18px;

  &.active,
  &.info {
    background: var(--gray-100);
    color: var(--gray-700);
  }

  &.success {
    background: var(--color-success-50);
    color: var(--color-success-700);
  }

  &.failed,
  &.error {
    background: var(--color-error-50);
    color: var(--color-error-700);
  }
}

.flow-loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 148px;
  padding: 16px;
  flex-direction: column;
  gap: 6px;
  color: var(--gray-600);
  text-align: center;

  .loading-state-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    margin-bottom: 4px;
    border-radius: 50%;
    background: var(--gray-100);
  }

  strong {
    color: var(--gray-800);
    font-size: 14px;
    line-height: 20px;
  }

  span {
    color: var(--gray-500);
    font-size: 12px;
    line-height: 18px;
  }

  &.failed {
    color: var(--color-error-700);

    .loading-state-icon {
      background: var(--color-error-50);
    }
  }
}

.review-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--gray-800);

  strong {
    font-size: 13px;
  }

  span {
    color: var(--gray-500);
    font-size: 12px;
  }
}

.review-list {
  overflow: hidden;
  gap: 0;
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  background: var(--gray-0);
}

.review-item {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  min-height: 56px;
  padding: 10px 12px;
  gap: 12px;
  border-bottom: 1px solid var(--gray-100);

  &:last-child {
    border-bottom: 0;
  }

  &.failed {
    background: var(--color-error-50);
  }
}

.review-warning {
  width: 100%;
  color: var(--color-warning-900);
  font-size: 12px;
}

.review-remove-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 28px;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--gray-400);
  cursor: pointer;
  transition:
    color 160ms ease,
    background-color 160ms ease;

  &:hover {
    background: var(--gray-100);
    color: var(--gray-800);
  }

  &:focus-visible {
    outline: 2px solid var(--gray-500);
    outline-offset: 1px;
  }
}

.install-target-section,
.share-config-section {
  padding-top: 4px;

  h3 {
    margin: 0 0 9px;
    color: var(--gray-700);
    font-size: 13px;
    font-weight: 600;
  }
}

.install-target-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.install-target-option {
  display: flex;
  width: 100%;
  min-height: 88px;
  padding: 12px;
  flex-direction: column;
  gap: 5px;
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  background: var(--gray-0);
  color: var(--gray-500);
  cursor: pointer;
  text-align: left;
  transition:
    border-color 160ms ease,
    background-color 160ms ease;

  &:hover {
    border-color: var(--gray-300);
    background: var(--gray-25);
  }

  &.selected {
    border-color: var(--main-500);
    background: var(--main-30);
  }

  &:focus-visible {
    outline: 2px solid var(--main-400);
    outline-offset: 1px;
  }

  > span:last-child {
    font-size: 12px;
    line-height: 18px;
  }
}

.install-target-title {
  color: var(--gray-800);
  font-size: 13px;
  font-weight: 600;

  b {
    margin-left: 4px;
    padding: 1px 5px;
    border-radius: 4px;
    background: var(--main-100);
    color: var(--main-800);
    font-size: 10px;
    font-weight: 600;
  }
}

.personal-install-note {
  padding: 9px 11px;
  border: 1px solid var(--main-100);
  border-radius: 6px;
  background: var(--main-30);
  color: var(--main-800);
  font-size: 12px;
  line-height: 18px;
}

.flow-alert {
  padding: 9px 11px;
  border: 1px solid var(--color-error-200);
  border-radius: 6px;
  background: var(--color-error-50);
  color: var(--color-error-700);
  font-size: 12px;
}

.install-flow-footer {
  padding-top: 14px;
}

.footer-summary {
  color: var(--gray-500);
  font-size: 12px;
}

.footer-actions {
  display: flex;
  gap: 8px;
}

.spin {
  animation: flow-spin 1s linear infinite;
}

@keyframes flow-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .spin {
    animation-duration: 2.4s;
  }
}

@media (max-width: 600px) {
  .install-flow-shell {
    min-height: calc(100vh - 48px);
    max-height: none;
  }

  .install-flow-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .footer-actions {
    justify-content: flex-end;
    flex-wrap: wrap;
  }

  .install-target-options {
    grid-template-columns: 1fr;
  }
}
</style>

<style lang="less">
body:has(.skill-install-flow-modal) {
  overflow-x: hidden;
}

@media (max-width: 600px) {
  .skill-install-flow-modal {
    top: 0;
    width: 100% !important;
    max-width: none;
    margin: 0;
    padding: 0;

    .ant-modal-content {
      min-height: 100vh;
      border-radius: 0;
    }
  }
}
</style>
