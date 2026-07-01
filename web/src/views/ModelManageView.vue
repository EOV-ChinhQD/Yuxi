<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import PageHeader from '@/components/shared/PageHeader.vue'
import AgentManagePanel from '@/components/model-management/AgentManagePanel.vue'
import ModelProviderManagePanel from '@/components/model-management/ModelProviderManagePanel.vue'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const activeTab = ref('agents')
const agentPanelRef = ref(null)
const providerPanelRef = ref(null)

const modelManageTabs = computed(() => {
  const tabs = [{ key: 'agents', label: 'đại lý' }]
  if (userStore.isAdmin) tabs.push({ key: 'providers', label: 'nhà cung cấp mô hình' })
  return tabs
})

const activePanel = computed(() =>
  activeTab.value === 'providers' ? providerPanelRef.value : agentPanelRef.value
)

const activeLoading = computed(() => activePanel.value?.loading || false)
const activeStats = computed(() => activePanel.value?.stats || {})

const normalizeTab = (tab) => {
  if (tab === 'providers' && userStore.isAdmin) return 'providers'
  return 'agents'
}

watch(
  () => [route.query.tab, userStore.isAdmin],
  ([tab]) => {
    const nextTab = normalizeTab(tab)
    if (activeTab.value !== nextTab) activeTab.value = nextTab
  },
  { immediate: true }
)

watch(activeTab, (tab) => {
  const nextTab = normalizeTab(tab)
  if (nextTab !== tab) {
    activeTab.value = nextTab
    return
  }
  if (route.query.tab === nextTab) return
  router.replace({ query: { ...route.query, tab: nextTab } })
})
</script>

<template>
  <div class="model-manage-view">
    <PageHeader
      v-model:active-key="activeTab"
      title="Quản lý đại lý"
      :tabs="modelManageTabs"
      :loading="activeLoading"
      :show-border="true"
      aria-label="Chuyển đổi chế độ xem quản lý đại lý"
    >
      <template #info>
        <div v-if="activeTab === 'agents'" class="summary-strip">
          <span>{{ activeStats.total || 0 }} đại lý</span>
          <span>{{ activeStats.global || 0 }} tình hình chung</span>
          <span v-if="activeStats.builtin">{{ activeStats.builtin }} tích hợp sẵn</span>
          <span>{{ activeStats.manageable || 0 }} có thể quản lý được</span>
        </div>
        <div v-else class="summary-strip">
          <span>{{ activeStats.total || 0 }} nhà cung cấp</span>
          <span>{{ activeStats.enabled || 0 }} đã bật</span>
          <span v-if="activeStats.warning > 0" class="warning-count">
            {{ activeStats.warning }} Chứng từ bị thiếu
          </span>
          <span>{{ activeStats.models || 0 }} mô hình</span>
        </div>
      </template>
    </PageHeader>

    <div class="model-manage-content">
      <div v-show="activeTab === 'agents'" class="tab-panel">
        <AgentManagePanel ref="agentPanelRef" />
      </div>
      <div v-if="userStore.isAdmin && activeTab === 'providers'" class="tab-panel">
        <ModelProviderManagePanel ref="providerPanelRef" />
      </div>
    </div>
  </div>
</template>

<style lang="less" scoped>
.model-manage-view {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  background: var(--gray-0);
  color: var(--gray-1000);
}

.model-manage-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;

  .tab-panel {
    height: 100%;
    min-height: 0;
    overflow-y: auto;
  }
}

.summary-strip {
  display: flex;
  gap: 8px;

  span {
    padding: 6px 10px;
    border: 1px solid var(--gray-100);
    border-radius: 7px;
    background: var(--gray-10);
    color: var(--gray-700);
    font-size: 12px;
    line-height: 18px;
  }

  .warning-count {
    background: var(--color-warning-50);
    border-color: var(--color-warning-100);
    color: var(--color-warning-700);
  }
}
</style>
