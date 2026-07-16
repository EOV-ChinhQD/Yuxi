<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { Globe } from 'lucide-vue-next'
import { message } from 'ant-design-vue'
import { modelProviderApi } from '@/apis/system_api'
import { modelIcons } from '@/utils/modelIcon'

const props = defineProps({
  open: {
    type: Boolean,
    required: true
  },
  activeProviders: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:open', 'select'])

const loading = ref(false)
const builtinProviders = ref([])

const handleCancel = () => {
  emit('update:open', false)
}

const loadBuiltinProviders = async () => {
  loading.value = true
  try {
    const response = await modelProviderApi.getBuiltinProviders()
    builtinProviders.value = response.data || []
  } catch (error) {
    message.error(error.message || 'Không thể tải danh sách nhà cung cấp tích hợp sẵn')
  } finally {
    loading.value = false
  }
}

// Map provider_id to currently active provider count
const activeCounts = computed(() => {
  const counts = {}
  for (const p of props.activeProviders) {
    const pid = p.provider_id
    counts[pid] = (counts[pid] || 0) + 1
  }
  return counts
})

const getIconUrl = (providerId) => {
  return modelIcons[providerId] || modelIcons.default
}

const selectProvider = (provider) => {
  emit('select', { mode: 'quick', provider })
  emit('update:open', false)
}

const selectCustom = () => {
  emit('select', { mode: 'full', provider: null })
  emit('update:open', false)
}

watch(
  () => props.open,
  (newVal) => {
    if (newVal && builtinProviders.value.length === 0) {
      loadBuiltinProviders()
    }
  }
)

onMounted(() => {
  if (props.open) {
    loadBuiltinProviders()
  }
})
</script>

<template>
  <a-modal
    :open="open"
    title="Chọn nhà cung cấp mô hình"
    :width="680"
    :footer="null"
    @cancel="handleCancel"
    class="provider-catalog-modal"
  >
    <div v-if="loading" class="loading-container">
      <a-spin size="large" tip="Đang tải danh mục..." />
    </div>
    <div v-else class="catalog-content">
      <div class="catalog-grid">
        <!-- Predefined Providers -->
        <div
          v-for="provider in builtinProviders"
          :key="provider.provider_id"
          class="provider-card"
          @click="selectProvider(provider)"
        >
          <div class="provider-logo">
            <img :src="getIconUrl(provider.provider_id)" :alt="provider.display_name" />
          </div>
          <div class="provider-name">{{ provider.display_name }}</div>
          <div v-if="activeCounts[provider.provider_id]" class="provider-badge">
            Đã thêm ({{ activeCounts[provider.provider_id] }})
          </div>
        </div>

        <!-- Custom Provider -->
        <div class="provider-card custom-card" @click="selectCustom">
          <div class="provider-logo custom-logo">
            <Globe :size="32" class="custom-icon" />
          </div>
          <div class="provider-name">Custom OpenAI Compatible</div>
          <div class="provider-subtitle">Tùy chỉnh URL và các tham số khác</div>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<style lang="less" scoped>
.provider-catalog-modal {
  :deep(.ant-modal-body) {
    padding: 24px;
  }
}

.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 40px 0;
}

.catalog-content {
  max-height: 480px;
  overflow-y: auto;
  padding: 4px;
}

.catalog-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
}

.provider-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px 12px;
  background: var(--gray-5);
  border: 1px solid var(--gray-150);
  border-radius: 12px;
  cursor: pointer;
  position: relative;
  transition: all 0.2s ease-in-out;
  text-align: center;

  &:hover {
    border-color: var(--main-color);
    background: var(--main-5);
    box-shadow: 0 4px 12px rgba(0, 106, 255, 0.08);
    transform: translateY(-2px);
  }

  .provider-logo {
    width: 48px;
    height: 48px;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    justify-content: center;

    img {
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
    }
  }

  .provider-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--gray-900);
    line-height: 20px;
  }

  .provider-badge {
    position: absolute;
    top: 8px;
    right: 8px;
    background: var(--main-20);
    color: var(--main-color);
    font-size: 11px;
    padding: 2px 6px;
    border-radius: 6px;
    font-weight: 500;
  }
}

.custom-card {
  border-style: dashed;
  background: transparent;

  &:hover {
    background: var(--main-5);
  }

  .custom-logo {
    background: var(--gray-100);
    border-radius: 50%;
    width: 48px;
    height: 48px;
    color: var(--gray-600);
    transition: all 0.2s ease-in-out;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  &:hover .custom-logo {
    background: var(--main-20);
    color: var(--main-color);
  }

  .provider-subtitle {
    font-size: 11px;
    color: var(--gray-500);
    margin-top: 4px;
    line-height: 16px;
  }
}
</style>
