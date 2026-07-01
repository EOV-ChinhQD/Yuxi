<template>
  <div class="attachment-options">
    <div class="option-item" :class="{ disabled: disabled }" @click="handleAttachmentClick">
      <a-tooltip title="Hỗ trợ mọi định dạng tập tin ≤ 5 MB" placement="right">
        <div class="option-content">
          <FileText :size="14" class="option-icon" />
          <span class="option-text">Thêm tệp đính kèm</span>
        </div>
      </a-tooltip>
    </div>

    <div class="option-item" @click="handleImageUpload">
      <a-tooltip title="hỗ trợ jpg/jpeg/png/gif， ≤ 5 MB" placement="right">
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
import { multimodalApi } from '@/apis/agent_api'

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

// Xử lý tải lên hình ảnh
const handleImageUpload = () => {
  if (props.disabled) return

  // Tạo đầu vào tập tin ẩn
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
    // Xác minh kích thước tập tin（10MB）
    if (file.size > 10 * 1024 * 1024) {
      message.error('Tệp hình ảnh quá lớn，Vui lòng chọn ít hơn10MBhình ảnh')
      return
    }

    // Xác minh loại tệp
    if (!file.type.startsWith('image/')) {
      message.error('Vui lòng chọn một tệp hình ảnh hợp lệ')
      return
    }

    message.loading({ content: 'Đang xử lý hình ảnh...', key: 'image-upload' })

    const result = await multimodalApi.uploadImage(file)

    if (result.success) {
      message.success({
        content: 'Xử lý hình ảnh thành công',
        key: 'image-upload',
        duration: 2
      })

      // Gửi sự kiện tải lên thành công，Chứa dữ liệu hình ảnh đã được xử lý
      emit('upload-image', {
        success: true,
        imageContent: result.image_content,
        thumbnailContent: result.thumbnail_content,
        width: result.width,
        height: result.height,
        format: result.format,
        mimeType: result.mime_type || file.type,
        sizeBytes: result.size_bytes,
        originalName: file.name
      })

      // Gửi sự kiện thông báo tải lên thành công，Dùng để đóng bảng tùy chọn
      emit('upload-image-success')
    } else {
      message.error({
        content: `Xử lý hình ảnh không thành công: ${result.error}`,
        key: 'image-upload'
      })
    }
  } catch (error) {
    console.error('Tải hình ảnh lên không thành công:', error)
    message.error({
      content: `Tải hình ảnh lên không thành công: ${error.message || 'lỗi không xác định'}`,
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
