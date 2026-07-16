<template>
  <div class="attachment-options">
    <div class="option-item" :class="{ disabled: disabled }" @click="handleAttachmentClick">
      <a-tooltip title="Hỗ trợ mọi định dạng file ≤ 5 MB" placement="right">
        <div class="option-content">
          <FileText :size="14" class="option-icon" />
          <span class="option-text">Thêm tệp đính kèm</span>
        </div>
      </a-tooltip>
    </div>

    <div class="option-item" @click="handleImageUpload">
      <a-tooltip title="Hỗ trợ jpg/jpeg/png/gif, ≤ 5 MB" placement="right">
        <div class="option-content">
          <Image :size="14" class="option-icon" />
          <span class="option-text">Tải ảnh lên</span>
        </div>
      </a-tooltip>
    </div>
  </div>
</template>

<script setup>
import { FileText, Image } from 'lucide-vue-next'
import { message } from 'ant-design-vue'
import { uploadMultimodalImage } from '@/utils/multimodal_image_upload'

const props = defineProps({
  disabled: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['upload', 'upload-image', 'upload-image-success'])

const handleAttachmentClick = () => {
  if (props.disabled) return
  emit('upload')
}

// Đang xử lý tải lên hình ảnh
const handleImageUpload = () => {
  if (props.disabled) return

  // Tạo trường nhập tệp ẩn
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'
  input.multiple = false
  input.style.display = 'none'

  input.onchange = async (event) => {
    const file = event.target.files[0]
    if (file) {
      await processImageUpload(file)
    }
    document.body.removeChild(input)
  }

  document.body.appendChild(input)
  input.click()

  emit('upload-image')
}

// Xử lý logic tải lên hình ảnh
const processImageUpload = async (file) => {
  try {
    const imageData = await uploadMultimodalImage(file)
    if (!imageData) return

    // Gửi sự kiện tải lên thành công, bao gồm dữ liệu hình ảnh đã xử lý
    emit('upload-image', imageData)

    // Phát sự kiện thông báo tải lên thành công, để đóng bảng lựa chọn
    emit('upload-image-success')
  } catch (error) {
    console.error('Tải lên hình ảnh thất bại:', error)
    message.error({
      content: `Tải lên hình ảnh thất bại: ${error.message || 'Lỗi không xác định'}`,
      key: 'image-upload'
    })
  }
}
</script>

<style lang="less" scoped>
.attachment-options {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 120px;
}

.option-item {
  cursor: pointer;
  transition: all 0.2s ease;

  &.disabled {
    cursor: not-allowed;
    opacity: 0.5;

    .option-content {
      color: var(--gray-400);
    }
  }
}

.option-content {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  color: var(--gray-700);
  font-size: 12px;
  border-radius: 6px;
  transition: all 0.15s ease;

  .option-item:hover & {
    color: var(--main-color);
    background-color: var(--gray-50);
  }
}

.option-icon {
  flex-shrink: 0;
  color: inherit;
}

.option-text {
  font-weight: 500;
}
</style>
