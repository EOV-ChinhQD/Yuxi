<template>
  <a-modal
    v-model:open="visible"
    title="Tải lên điểm chuẩn đánh giá"
    width="600px"
    :mask-closable="!uploading"
    :closable="!uploading"
    @cancel="handleCancel"
  >
    <a-form ref="formRef" :model="formState" :rules="rules" layout="vertical">
      <a-form-item label="Tên điểm chuẩn" name="name">
        <a-input
          v-model:value="formState.name"
          placeholder="Vui lòng nhập tên điểm chuẩn đánh giá"
        />
      </a-form-item>

      <a-form-item label="Mô tả" name="description">
        <a-textarea
          v-model:value="formState.description"
          placeholder="Vui lòng nhập mô tả về điểm chuẩn đánh giá（Tùy chọn）"
          :rows="3"
        />
      </a-form-item>

      <a-form-item label="Tệp điểm chuẩn" name="file">
        <a-upload-dragger
          v-model:fileList="fileList"
          name="file"
          :multiple="false"
          accept=".jsonl"
          :before-upload="beforeUpload"
          @remove="handleRemove"
        >
          <UploadCloud class="upload-icon" />
          <p class="ant-upload-text">Bấm hoặc kéo JSONL Tải tập tin lên khu vực này</p>
          <p class="ant-upload-hint">
            mỗi dòng một cái JSON vật thể，Chỉ hỗ trợ .jsonl，tối đa 100MB
          </p>
        </a-upload-dragger>
      </a-form-item>
    </a-form>
    <template #footer>
      <div class="benchmark-modal-footer">
        <div class="benchmark-help-text">
          Cần biết định dạng chuẩn đánh giá？Xem
          <a
            class="benchmark-help-link"
            href="https://xerrors.github.io/Yuxi/intro/evaluation.html"
            target="_blank"
            rel="noopener noreferrer"
          >
            Hướng dẫn sử dụng
          </a>
        </div>
        <div class="footer-actions">
          <a-button :disabled="uploading" @click="handleCancel">Hủy bỏ</a-button>
          <a-button type="primary" :loading="uploading" :disabled="uploading" @click="handleUpload">
            tải lên
          </a-button>
        </div>
      </div>
    </template>
  </a-modal>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import { UploadCloud } from 'lucide-vue-next'
import { evaluationApi } from '@/apis/knowledge_api'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  kbId: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['update:visible', 'success'])

// Dữ liệu đáp ứng
const formRef = ref()
const fileList = ref([])
const uploading = ref(false)

const formState = reactive({
  name: '',
  description: '',
  file: null
})

// quy tắc xác thực biểu mẫu
const rules = {
  name: [
    { required: true, message: 'Vui lòng nhập tên điểm chuẩn', trigger: 'blur' },
    {
      min: 2,
      max: 100,
      message: 'Độ dài tên cơ sở phải nằm trong2-100giữa các ký tự',
      trigger: 'blur'
    }
  ],
  file: [{ required: true, message: 'Vui lòng chọn một tập tin điểm chuẩn', trigger: 'change' }]
}

// Ràng buộc hai chiềuvisible
const visible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

// Xác minh trước khi tải lên tập tin
const beforeUpload = async (file) => {
  // Kiểm tra loại tập tin
  if (!file.name.endsWith('.jsonl')) {
    message.error('Chỉ hỗ trợ JSONL tập tin định dạng')
    return false
  }

  // Kiểm tra kích thước tập tin（giới hạn ở100MB）
  const isLt100M = file.size / 1024 / 1024 < 100
  if (!isLt100M) {
    message.error('Kích thước tệp không thể vượt quá 100MB')
    return false
  }

  try {
    // Đọc định dạng xác minh nội dung tập tin
    const content = await new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = (e) => resolve(e.target.result)
      reader.onerror = () => reject(new Error('Đọc tệp không thành công'))
      reader.readAsText(file)
    })

    const lines = content.trim().split('\n')

    // Xác minh rằng có ít nhất một hàng
    if (lines.length === 0) {
      message.error('Tệp không thể trống')
      return false
    }

    // Xác minhJSONđịnh dạng
    for (let i = 0; i < Math.min(5, lines.length); i++) {
      const line = lines[i].trim()
      if (line) {
        JSON.parse(line)
      }
    }

    // Xác minh đã được thông qua，tập tin cài đặt
    formState.file = file
    return true
  } catch (error) {
    if (error instanceof SyntaxError) {
      message.error('Lỗi định dạng tệp，vui lòng kiểm traJSONLđịnh dạng')
    } else {
      message.error('Xác minh tệp không thành công: ' + error.message)
    }
    return false
  }
}

// Xóa tập tin
const handleRemove = () => {
  formState.file = null
}

// Tải tập tin lên
const handleUpload = async () => {
  try {
    // xác nhận mẫu
    await formRef.value.validate()

    if (!formState.file) {
      message.error('Vui lòng chọn một tập tin điểm chuẩn')
      return
    }

    uploading.value = true

    const response = await evaluationApi.uploadDataset(props.kbId, formState.file, {
      name: formState.name,
      description: formState.description
    })

    if (response.message === 'success') {
      message.success('Tải lên thành công')
      handleCancel()
      emit('success')
    } else {
      message.error(response.message || 'Tải lên không thành công')
    }
  } catch (error) {
    console.error('Tải lên không thành công:', error)
    message.error('Tải lên không thành công')
  } finally {
    uploading.value = false
  }
}

// Hủy thao tác
const handleCancel = () => {
  visible.value = false
  resetForm()
}

// Đặt lại biểu mẫu
const resetForm = () => {
  formRef.value?.resetFields()
  fileList.value = []
  formState.file = null
  uploading.value = false
}

// màn hìnhvisiblethay đổi
watch(visible, (val) => {
  if (!val) {
    resetForm()
  }
})
</script>

<style lang="less" scoped>
:deep(.ant-upload-dragger) {
  padding: 24px 16px;
  border-color: var(--gray-150);
  background: var(--gray-0);
  transition: all 0.2s ease;

  &:hover {
    border-color: var(--main-color);
    background: var(--main-10);
  }

  .ant-upload-text {
    margin: 8px 0 4px;
    font-size: 15px;
    font-weight: 500;
    color: var(--gray-800);
  }

  .ant-upload-hint {
    color: var(--gray-500);
  }
}

.upload-icon {
  width: 44px;
  height: 44px;
  color: var(--main-color);
}

.benchmark-modal-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.benchmark-help-text {
  font-size: 13px;
  line-height: 1.5;
  color: var(--gray-600);
}

.benchmark-help-link {
  margin-left: 2px;
}

.footer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

@media (max-width: 640px) {
  .benchmark-modal-footer {
    align-items: flex-start;
    flex-direction: column;
  }

  .footer-actions {
    align-self: flex-end;
  }
}
</style>
