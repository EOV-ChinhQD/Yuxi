<template>
  <div class="skill-settings-section">
    <div class="section-title">Skill Configuration</div>

    <section class="source-panel">
      <template v-if="sourceOption">
        <div class="source-header">
          <div class="source-copy">
            <h4>Remote Source Whitelist</h4>
            <p>Only domain names on the list can load and install skills remotely.</p>
          </div>
          <a-button v-if="!isEditing" type="text" size="small" @click="startEditing">
            <Pencil :size="14" />
            Edit
          </a-button>
        </div>

        <div v-for="field in sourceFields" :key="field.key" class="source-content">
          <template v-if="isEditing">
            <a-select
              v-model:value="draftValue[field.key]"
              class="domain-select"
              mode="tags"
              :aria-label="field.label"
              :token-separators="[',', ' ', '\n']"
              placeholder="Enter domain name and press Enter, e.g. github.com"
              :options="[]"
            />
            <div class="edit-footer">
              <span>Exact domain match; clearing and saving will disable remote installation.</span>
              <div class="edit-actions">
                <a-button size="small" :disabled="isSaving" @click="cancelEditing"> Cancel </a-button>
                <a-button type="primary" size="small" :loading="isSaving" @click="saveOption">
                  Save
                </a-button>
              </div>
            </div>
          </template>
          <div
            v-else-if="getFieldValue(field).length"
            class="host-list"
            aria-label="Allowed source domains"
          >
            <a-tag v-for="host in getFieldValue(field)" :key="host" class="host-tag">
              {{ host }}
            </a-tag>
          </div>
          <div v-else class="empty-value">No domains configured; remote installation is disabled</div>
        </div>
      </template>

      <div v-else class="panel-state">
        {{ isLoading ? 'Loading configuration...' : 'Remote Skill source configuration not yet initialized' }}
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { Pencil } from 'lucide-vue-next'
import { configOptionsApi } from '@/apis/system_api'

const SOURCE_OPTION_KEY = 'remote_skill_source_policy'

const sourceOption = ref(null)
const isEditing = ref(false)
const isLoading = ref(true)
const isSaving = ref(false)
const draftValue = ref({})

const sourceFields = computed(() => sourceOption.value?.params?.fields || [])

/** Return saved value; display backend default if not yet saved. */
const getFieldValue = (field) => {
  const value = sourceOption.value?.value || {}
  if (Object.prototype.hasOwnProperty.call(value, field.key)) return value[field.key]
  return field.default || []
}

/** Load remote skill source configuration. */
const loadOption = async () => {
  try {
    const data = await configOptionsApi.getOptions()
    sourceOption.value = (data.options || []).find((option) => option.key === SOURCE_OPTION_KEY)
  } catch (error) {
    message.error(error.message || 'Failed to load Skill configuration')
  } finally {
    isLoading.value = false
  }
}

/** Enter editing mode and clone current domains to avoid modifying API data directly. */
const startEditing = () => {
  draftValue.value = Object.fromEntries(
    sourceFields.value.map((field) => [field.key, [...getFieldValue(field)]])
  )
  isEditing.value = true
}

/** Cancel editing. */
const cancelEditing = () => {
  isEditing.value = false
  draftValue.value = {}
}

/** Save source domains and refresh with server-normalized values. */
const saveOption = async () => {
  isSaving.value = true
  try {
    const data = await configOptionsApi.updateOption(SOURCE_OPTION_KEY, draftValue.value)
    sourceOption.value = data.option
    cancelEditing()
    message.success('Skill source configuration saved')
  } catch (error) {
    message.error(error.message || 'Failed to save Skill configuration')
  } finally {
    isSaving.value = false
  }
}

onMounted(loadOption)
</script>

<style lang="less" scoped>
.skill-settings-section {
  margin-top: 24px;

  &.first-section {
    margin-top: 0;
  }
}

.section-title {
  margin: 0 0 10px;
  color: var(--gray-900);
  font-size: 15px;
  font-weight: 600;
}

.source-panel {
  padding: 14px 16px;
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  background: var(--gray-0);
}

.source-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;

  h4,
  p {
    margin: 0;
  }

  h4 {
    color: var(--gray-900);
    font-size: 13px;
    font-weight: 500;
  }

  p {
    margin-top: 4px;
    color: var(--color-text-secondary);
    font-size: 12px;
    line-height: 1.5;
  }

  :deep(.ant-btn) {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    color: var(--gray-600);

    &:hover,
    &:focus-visible {
      color: var(--main-700);
      background: var(--main-10);
    }
  }
}

.source-content {
  margin-top: 14px;
}

.domain-select {
  width: 100%;
}

.edit-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 10px;

  > span {
    color: var(--color-text-secondary);
    font-size: 12px;
    line-height: 1.5;
  }
}

.edit-actions {
  display: flex;
  flex: none;
  gap: 8px;
}

.host-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.host-tag {
  margin: 0;
  padding: 3px 9px;
  border-color: var(--gray-150);
  border-radius: 6px;
  background: var(--gray-50);
  color: var(--gray-700);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  line-height: 18px;
}

.empty-value,
.panel-state {
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.panel-state {
  padding: 4px 0;
}

@media (max-width: 680px) {
  .edit-footer {
    align-items: flex-start;
    flex-direction: column;
  }

  .edit-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
