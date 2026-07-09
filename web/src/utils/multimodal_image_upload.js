import { message } from 'ant-design-vue'
import { multimodalApi } from '@/apis/agent_api'

const MAX_IMAGE_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024

export const uploadMultimodalImage = async (file) => {
  if (!file) return null

  if (file.size > MAX_IMAGE_UPLOAD_SIZE_BYTES) {
    message.error('Tệp ảnh quá lớn, vui lòng chọn nhỏ hơn10MBcủa hình ảnh')
    return null
  }

  if (!file.type?.startsWith('image/')) {
    message.error('Vui lòng chọn file hình ảnh hợp lệ')
    return null
  }

  try {
    message.loading({ content: 'Đang xử lý hình ảnh...', key: 'image-upload' })

    const result = await multimodalApi.uploadImage(file)
    if (!result.success) {
      message.error({
        content: `Xử lý hình ảnh thất bại: ${result.error}`,
        key: 'image-upload'
      })
      return null
    }

    message.success({
      content: 'Xử lý hình ảnh thành công',
      key: 'image-upload',
      duration: 2
    })

    return {
      success: true,
      imageContent: result.image_content,
      thumbnailContent: result.thumbnail_content,
      width: result.width,
      height: result.height,
      format: result.format,
      mimeType: result.mime_type || file.type,
      sizeBytes: result.size_bytes,
      originalName: file.name || result.original_filename || 'pasted-image'
    }
  } catch (error) {
    console.error('Tải lên hình ảnh thất bại:', error)
    message.error({
      content: `Tải lên hình ảnh thất bại: ${error.message || 'Lỗi không xác định'}`,
      key: 'image-upload'
    })
    return null
  }
}
