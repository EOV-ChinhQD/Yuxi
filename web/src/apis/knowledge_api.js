import { apiGet, apiAdminGet, apiAdminPost, apiAdminPut, apiAdminDelete, apiRequest } from './base'

/**
 * Quản lý cơ sở tri thứcAPImô-đun
 * Bao gồm quản lý cơ sở dữ liệu、Quản lý tài liệu、Giao diện truy vấn và các chức năng khác
 */

// =============================================================================
// === Nhóm quản lý cơ sở dữ liệu ===
// =============================================================================

export const databaseApi = {
  /**
   * Nhận tất cả các cơ sở kiến ​​thức
   * @returns {Promise} - Danh sách cơ sở kiến thức
   */
  getDatabases: async () => {
    return apiAdminGet('/api/knowledge/databases')
  },

  /**
   * Tạo nền tảng kiến thức
   * @param {Object} databaseData - dữ liệu cơ sở tri thức
   * @returns {Promise} - Tạo kết quả
   */
  createDatabase: async (databaseData) => {
    return apiAdminPost('/api/knowledge/databases', databaseData)
  },

  /**
   * Nhận thông tin chi tiết về cơ sở kiến thức
   * @param {string} kbId - cơ sở tri thứcID
   * @returns {Promise} - Thông tin cơ sở kiến thức
   */
  getDatabaseInfo: async (kbId) => {
    return apiAdminGet(`/api/knowledge/databases/${kbId}`)
  },

  /**
   * Sửa số liệu thống kê tập tin cơ sở kiến thức
   * @param {string} kbId - cơ sở tri thứcID
   * @returns {Promise} - Kết quả sửa chữa
   */
  repairDatabaseStats: async (kbId) => {
    return apiAdminPost(`/api/knowledge/databases/${kbId}/stats/repair`, {})
  },

  /**
   * Cập nhật thông tin cơ sở kiến thức
   * @param {string} kbId - cơ sở tri thứcID
   * @param {Object} updateData - Cập nhật dữ liệu
   * @returns {Promise} - Cập nhật kết quả
   */
  updateDatabase: async (kbId, updateData) => {
    return apiAdminPut(`/api/knowledge/databases/${kbId}`, updateData)
  },

  /**
   * Xóa cơ sở kiến thức
   * @param {string} kbId - cơ sở tri thứcID
   * @returns {Promise} - Xóa kết quả
   */
  deleteDatabase: async (kbId) => {
    return apiAdminDelete(`/api/knowledge/databases/${kbId}`)
  },

  /**
   * sử dụng AI Tạo hoặc tối ưu hóa các mô tả cơ sở kiến thức
   * @param {string} name - Tên cơ sở kiến thức
   * @param {string} currentDescription - mô tả hiện tại（Tùy chọn）
   * @param {Array} fileList - danh sách tập tin（Tùy chọn）
   * @returns {Promise} - Tạo kết quả
   */
  generateDescription: async (name, currentDescription = '', fileList = []) => {
    return apiAdminPost('/api/knowledge/generate-description', {
      name,
      current_description: currentDescription,
      file_list: fileList
    })
  },

  /**
   * Lấy danh sách cơ sở tri thức mà người dùng hiện tại có quyền truy cập（cho cấu hình đại lý）
   * @returns {Promise} - Danh sách cơ sở kiến thức có thể truy cập
   */
  getAccessibleDatabases: async () => {
    return apiGet('/api/knowledge/databases/accessible')
  }
}

// =============================================================================
// === Nhóm quản lý văn bản ===
// =============================================================================

const buildQuery = (params) => {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      query.set(key, String(value))
    }
  })
  return query.toString()
}

export const documentApi = {
  /**
   * Lấy danh sách tài liệu cơ sở kiến thức theo phân trang
   * @param {string} kbId - cơ sở tri thứcID
   * @param {Object} params - tham số truy vấn
   * @returns {Promise} - Danh sách tài liệu
   */
  listDocuments: async (kbId, params = {}) => {
    const query = buildQuery(params)
    return apiAdminGet(`/api/knowledge/databases/${kbId}/documents${query ? `?${query}` : ''}`)
  },

  /**
   * Kiểm tra xem tên tệp hoặc đường dẫn tương đối đã chỉ định có tồn tại trong cơ sở kiến ​​thức không
   * @param {string} kbId - cơ sở tri thứcID
   * @param {string} filename - Tên tệp hoặc đường dẫn tương đối
   * @returns {Promise} - Kết quả kiểm tra sự tồn tại
   */
  documentExists: async (kbId, filename) => {
    const query = buildQuery({ filename })
    return apiAdminGet(`/api/knowledge/databases/${kbId}/documents/exists?${query}`)
  },

  /**
   * Tạo thư mục
   * @param {string} kbId - cơ sở tri thứcID
   * @param {string} folderName - tên thư mục
   * @param {string} parentId - thư mục mẹID
   * @returns {Promise} - Tạo kết quả
   */
  createFolder: async (kbId, folderName, parentId = null) => {
    return apiAdminPost(`/api/knowledge/databases/${kbId}/folders`, {
      folder_name: folderName,
      parent_id: parentId
    })
  },

  /**
   * Thêm tài liệu vào cơ sở kiến thức
   * @param {string} kbId - cơ sở tri thứcID
   * @param {Array} items - Danh sách tài liệu
   * @param {Object} params - Thông số xử lý
   * @returns {Promise} - Thêm kết quả
   */
  addDocuments: async (kbId, items, params = {}) => {
    return apiAdminPost(`/api/knowledge/databases/${kbId}/documents`, {
      items,
      params
    })
  },

  /**
   * Thêm các tệp đã tải lên dưới dạng bản ghi tài liệu cơ sở kiến thức（Chưa được phân tích cú pháp、Không được lưu trữ trong kho）
   * @param {string} kbId - cơ sở tri thứcID
   * @param {Array} items - Tệp đã tải lên MinIO URL danh sách
   * @param {Object} params - Thêm thông số
   * @returns {Promise} - Thêm kết quả
   */
  addUploadedDocuments: async (kbId, items, params = {}) => {
    return apiAdminPost(`/api/knowledge/databases/${kbId}/documents/add`, {
      items,
      params
    })
  },

  /**
   * Nhận thông tin tài liệu
   * @param {string} kbId - cơ sở tri thứcID
   * @param {string} docId - Tài liệuID
   * @returns {Promise} - Thông tin tài liệu
   */
  getDocumentInfo: async (kbId, docId) => {
    return apiAdminGet(`/api/knowledge/databases/${kbId}/documents/${docId}`)
  },

  /**
   * Nhận thông tin cơ bản về tài liệu
   * @param {string} kbId - cơ sở tri thứcID
   * @param {string} docId - Tài liệuID
   * @returns {Promise} - Tài liệu thông tin cơ bản
   */
  getDocumentBasicInfo: async (kbId, docId) => {
    return apiAdminGet(`/api/knowledge/databases/${kbId}/documents/${docId}/basic`)
  },

  /**
   * Nhận nội dung phân tích tài liệu và phân đoạn
   * @param {string} kbId - cơ sở tri thứcID
   * @param {string} docId - Tài liệuID
   * @returns {Promise} - Thông tin nội dung tài liệu
   */
  getDocumentContent: async (kbId, docId) => {
    return apiAdminGet(`/api/knowledge/databases/${kbId}/documents/${docId}/content`)
  },

  /**
   * Xóa tài liệu
   * @param {string} kbId - cơ sở tri thứcID
   * @param {string} docId - Tài liệuID
   * @returns {Promise} - Xóa kết quả
   */
  deleteDocument: async (kbId, docId) => {
    return apiAdminDelete(`/api/knowledge/databases/${kbId}/documents/${docId}`)
  },

  /**
   * Xóa tài liệu theo đợt
   * @param {string} kbId - cơ sở tri thứcID
   * @param {Array} fileIds - tập tinIDdanh sách
   * @returns {Promise} - Xóa kết quả theo đợt
   */
  batchDeleteDocuments: async (kbId, fileIds) => {
    return apiRequest(
      `/api/knowledge/databases/${kbId}/documents/batch`,
      {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(fileIds)
      },
      true,
      'json'
    )
  },

  /**
   * Tải tài liệu xuống
   * @param {string} kbId - cơ sở tri thứcID
   * @param {string} docId - Tài liệuID
   * @returns {Promise} - Responsevật thể
   */
  downloadDocument: async (kbId, docId) => {
    return apiAdminGet(`/api/knowledge/databases/${kbId}/documents/${docId}/download`, {}, 'blob')
  },

  /**
   * Kích hoạt phân tích tài liệu theo cách thủ công
   * @param {string} kbId - cơ sở tri thứcID
   * @param {Array} fileIds - tập tinIDdanh sách
   * @returns {Promise} - Phân tích kết quả nhiệm vụ
   */
  parseDocuments: async (kbId, fileIds) => {
    return apiAdminPost(`/api/knowledge/databases/${kbId}/documents/parse`, fileIds)
  },

  /**
   * Kích hoạt thủ công việc phân tích cú pháp tất cả các tài liệu cần phân tích cú pháp
   * @param {string} kbId - cơ sở tri thứcID
   * @returns {Promise} - Phân tích kết quả nhiệm vụ
   */
  parsePendingDocuments: async (kbId) => {
    return apiAdminPost(`/api/knowledge/databases/${kbId}/documents/parse-pending`, {})
  },

  /**
   * Kích hoạt lưu trữ tài liệu theo cách thủ công
   * @param {string} kbId - cơ sở tri thứcID
   * @param {Array} fileIds - tập tinIDdanh sách
   * @param {Object} params - Thông số xử lý
   * @returns {Promise} - Kết quả nhiệm vụ kho bãi
   */
  indexDocuments: async (kbId, fileIds, params = {}) => {
    return apiAdminPost(`/api/knowledge/databases/${kbId}/documents/index`, {
      file_ids: fileIds,
      params
    })
  },

  /**
   * Kích hoạt thủ công việc lưu trữ tất cả các tài liệu sẽ được lưu trữ trong cơ sở dữ liệu
   * @param {string} kbId - cơ sở tri thứcID
   * @param {Object} params - Thông số xử lý
   * @returns {Promise} - Kết quả nhiệm vụ kho bãi
   */
  indexPendingDocuments: async (kbId, params = {}) => {
    return apiAdminPost(`/api/knowledge/databases/${kbId}/documents/index-pending`, {
      params
    })
  }
}

// =============================================================================
// === Nhóm xây dựng bản đồ ===
// =============================================================================

function graphBuildUrl(kbId, action) {
  return `/api/knowledge/databases/${kbId}/graph-build/${action}`
}

export const graphBuildApi = {
  getStatus: async (kbId) => {
    return apiAdminGet(graphBuildUrl(kbId, 'status'))
  },

  configure: async (kbId, data) => {
    return apiAdminPost(graphBuildUrl(kbId, 'config'), data)
  },

  startIndex: async (kbId, batchSize = 20) => {
    return apiAdminPost(graphBuildUrl(kbId, 'index'), {
      batch_size: batchSize
    })
  },

  reset: async (kbId, data) => {
    return apiAdminPost(graphBuildUrl(kbId, 'reset'), data)
  }
}

// =============================================================================
// === Nhóm bản đồ tư duy ===
// =============================================================================

export const mindmapApi = {
  getDatabases: async () => {
    return apiAdminGet('/api/knowledge/mindmap/databases')
  },

  getDatabaseFiles: async (kbId) => {
    return apiAdminGet(`/api/knowledge/databases/${kbId}/mindmap/files`)
  },

  generateMindmap: async (kbId, fileIds = [], userPrompt = '', incremental = false) => {
    return apiAdminPost(`/api/knowledge/databases/${kbId}/mindmap/generate`, {
      file_ids: fileIds,
      user_prompt: userPrompt,
      incremental
    })
  },

  getByDatabase: async (kbId) => {
    return apiAdminGet(`/api/knowledge/databases/${kbId}/mindmap`)
  },

  getDiff: async (kbId) => {
    return apiAdminGet(`/api/knowledge/databases/${kbId}/mindmap/diff`)
  }
}

// =============================================================================
// === Nhóm truy vấn ===
// =============================================================================

export const queryApi = {
  /**
   * Truy vấn cơ sở kiến thức
   * @param {string} kbId - cơ sở tri thứcID
   * @param {string} query - Văn bản truy vấn
   * @param {Object} meta - tham số truy vấn
   * @returns {Promise} - Kết quả truy vấn
   */
  queryKnowledgeBase: async (kbId, query, meta = {}) => {
    return apiAdminPost(`/api/knowledge/databases/${kbId}/query`, {
      query,
      meta
    })
  },

  /**
   * Kiểm tra cơ sở kiến thức truy vấn
   * @param {string} kbId - cơ sở tri thứcID
   * @param {string} query - Văn bản truy vấn
   * @param {Object} meta - tham số truy vấn
   * @returns {Promise} - Kết quả kiểm tra
   */
  queryTest: async (kbId, query, meta = {}) => {
    return apiAdminPost(`/api/knowledge/databases/${kbId}/query-test`, {
      query,
      meta
    })
  },

  /**
   * Nhận tham số truy vấn cơ sở kiến thức
   * @param {string} kbId - cơ sở tri thứcID
   * @returns {Promise} - tham số truy vấn
   */
  getKnowledgeBaseQueryParams: async (kbId) => {
    return apiAdminGet(`/api/knowledge/databases/${kbId}/query-params`)
  },

  /**
   * Cập nhật các tham số truy vấn cơ sở kiến thức
   * @param {string} kbId - cơ sở tri thứcID
   * @param {Object} params - tham số truy vấn
   * @returns {Promise} - Cập nhật kết quả
   */
  updateKnowledgeBaseQueryParams: async (kbId, params) => {
    return apiAdminPut(`/api/knowledge/databases/${kbId}/query-params`, params)
  },

  /**
   * Tạo câu hỏi kiểm tra cho cơ sở kiến thức
   * @param {string} kbId - cơ sở tri thứcID
   * @param {number} count - Số lượng câu hỏi được tạo，Mặc định10
   * @returns {Promise} - danh sách câu hỏi được tạo
   */
  generateSampleQuestions: async (kbId, count = 10) => {
    return apiAdminPost(`/api/knowledge/databases/${kbId}/sample-questions`, {
      count
    })
  },

  /**
   * Nhận câu hỏi kiểm tra từ cơ sở kiến thức
   * @param {string} kbId - cơ sở tri thứcID
   * @returns {Promise} - Danh sách câu hỏi
   */
  getSampleQuestions: async (kbId) => {
    return apiAdminGet(`/api/knowledge/databases/${kbId}/sample-questions`)
  }
}

// =============================================================================
// === Nhóm quản lý tập tin ===
// =============================================================================

export const fileApi = {
  /**
   * thu thập thông tin URL nội dung
   * @param {string} url - mục tiêu URL
   * @param {string} kbId - cơ sở tri thức ID
   * @returns {Promise} - Tìm nạp kết quả
   */
  fetchUrl: async (url, kbId = null) => {
    return apiAdminPost('/api/knowledge/files/fetch-url', {
      url,
      kb_id: kbId
    })
  },

  /**
   * Nhập tệp từ không gian làm việc vào cơ sở kiến thức MinIO Khu vực dàn dựng
   * @param {string} kbId - cơ sở tri thức ID
   * @param {Array<string>} paths - đường dẫn tập tin không gian làm việc
   * @returns {Promise} - Nhập kết quả
   */
  importWorkspaceFiles: async (kbId, paths) => {
    return apiAdminPost('/api/knowledge/files/import-workspace', {
      kb_id: kbId,
      paths
    })
  },

  /**
   * Tải tập tin lên
   * @param {File} file - đối tượng tập tin
   * @param {string} kbId - cơ sở tri thứcID（Tùy chọn）
   * @returns {Promise} - Tải kết quả lên
   */
  uploadFile: async (file, kbId = null) => {
    const formData = new FormData()
    formData.append('file', file)

    const url = kbId ? `/api/knowledge/files/upload?kb_id=${kbId}` : '/api/knowledge/files/upload'

    return apiAdminPost(url, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  /**
   * Nhận các loại tệp được hỗ trợ
   * @returns {Promise} - Danh sách các loại tập tin
   */
  getSupportedFileTypes: async () => {
    return apiAdminGet('/api/knowledge/files/supported-types')
  },

  /**
   * Tải lên thư mục（zipđịnh dạng）
   * @param {File} file - ziptập tin
   * @param {string} kbId - cơ sở tri thứcID
   * @returns {Promise} - Tải kết quả lên
   */
  uploadFolder: async (file, kbId) => {
    const formData = new FormData()
    formData.append('file', file)

    // sử dụng apiRequest Gửi trực tiếp FormData，Nhưng sử dụng xử lý lỗi thống nhất
    return apiRequest(
      `/api/knowledge/files/upload-folder?kb_id=${kbId}`,
      {
        method: 'POST',
        body: formData
        // Chưa đặt Content-Type，Hãy để trình duyệt tự động thiết lập boundary
      },
      true,
      'json'
    ) // Yêu cầu xác thực，Kỳ vọngJSONphản ứng
  },

  /**
   * Thư mục xử lý（Xử lý không đồng bộziptập tin）
   * @param {Object} data - Thông số xử lý
   * @param {string} data.file_path - Đã tải lênzipđường dẫn tập tin
   * @param {string} data.kb_id - cơ sở tri thứcID
   * @param {string} data.content_hash - Băm nội dung tệp
   * @returns {Promise} - Xử lý kết quả nhiệm vụ
   */
  processFolder: async ({ file_path, kb_id, content_hash }) => {
    return apiAdminPost('/api/knowledge/files/process-folder', {
      file_path,
      kb_id,
      content_hash
    })
  }
}

// =============================================================================
// === Nhóm loại cơ sở kiến thức ===
// =============================================================================

export const typeApi = {
  /**
   * Nhận các loại cơ sở kiến thức được hỗ trợ
   * @returns {Promise} - Danh sách các loại cơ sở tri thức
   */
  getKnowledgeBaseTypes: async () => {
    return apiAdminGet('/api/knowledge/types')
  },

  /**
   * Lấy cấu hình phân mảnh (chunk presets) được hỗ trợ
   * @returns {Promise} - Danh sách cấu hình phân mảnh
   */
  getChunkPresets: async () => {
    return apiAdminGet('/api/knowledge/chunk-presets')
  },

  /**
   * Lấy thông tin thống kê của cơ sở tri thức
   * @returns {Promise} - Thông tin thống kê
   */
  getStatistics: async () => {
    return apiAdminGet('/api/knowledge/stats')
  }
}

// =============================================================================
// === RAGNhóm đánh giá ===
// =============================================================================

export const evaluationApi = {
  uploadDataset: async (kbId, file, metadata = {}) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', metadata.name || '')
    formData.append('description', metadata.description || '')

    return apiAdminPost(`/api/evaluation/databases/${kbId}/datasets/upload`, formData)
  },

  listDatasets: async (kbId) => {
    return apiAdminGet(`/api/evaluation/databases/${kbId}/datasets`)
  },

  getDataset: async (kbId, datasetId, page = 1, pageSize = 50) => {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString()
    })
    return apiAdminGet(`/api/evaluation/databases/${kbId}/datasets/${datasetId}?${params}`)
  },

  deleteDataset: async (datasetId) => {
    return apiAdminDelete(`/api/evaluation/datasets/${datasetId}`)
  },

  downloadDataset: async (datasetId) => {
    return apiAdminGet(`/api/evaluation/datasets/${datasetId}/download`, {}, 'blob')
  },

  generateDataset: async (kbId, params) => {
    return apiAdminPost(`/api/evaluation/databases/${kbId}/datasets/generate`, params)
  },

  runEvaluation: async (kbId, params) => {
    return apiAdminPost(`/api/evaluation/databases/${kbId}/runs`, params)
  },

  listRuns: async (kbId) => {
    return apiAdminGet(`/api/evaluation/databases/${kbId}/runs`)
  },

  getRunResults: async (kbId, runId, params = {}) => {
    const queryParams = new URLSearchParams()

    if (params.page) queryParams.append('page', params.page)
    if (params.pageSize) queryParams.append('page_size', params.pageSize)
    if (params.errorOnly !== undefined) queryParams.append('error_only', params.errorOnly)

    const url = `/api/evaluation/databases/${kbId}/runs/${runId}${queryParams.toString() ? '?' + queryParams.toString() : ''}`
    return apiAdminGet(url)
  },

  deleteRun: async (kbId, runId) => {
    return apiAdminDelete(`/api/evaluation/databases/${kbId}/runs/${runId}`)
  }
}
