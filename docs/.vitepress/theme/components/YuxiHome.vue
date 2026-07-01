<script setup>
import { ref, computed } from 'vue'
import { withBase } from 'vitepress'

const GITHUB = 'https://github.com/xerrors/Yuxi'
const DEMO = 'https://www.bilibili.com/video/BV1TZEx6NEit/'

// nhân vật chủ chốt（Trình giữ chỗ，Sau đó được thay thế bằng dữ liệu thực）
const stats = [
  { value: '15+', label: 'nhà cung cấp mô hình' },
  { value: '7', label: 'Harness khả năng' },
  { value: 'MIT', label: 'Thỏa thuận nguồn mở' },
  { value: 'v0.7', label: 'Phiên bản hiện tại' }
]

// Harness trung tâm khả năng（bento）
const capabilities = [
  {
    icon: 'box', span: true,
    title: 'hệ thống tập tin hộp cát',
    desc: 'Mỗi phiên có một hệ thống tệp ảo độc lập（workspace / uploads / outputs），Vị trí tự động sản phẩm thông minh，văn bản hỗ trợ、hình ảnh、PDF、HTML Xem trước và tải xuống trực tuyến。',
    tags: ['Xem trước', 'Tải xuống', 'Artifacts sản phẩm'],
    shot: 'https://xerrors.oss-cn-shanghai.aliyuncs.com/github/image-20260604203704426.png'
  },
  {
    icon: 'sparkles',
    title: 'Skills Hệ thống kỹ năng',
    desc: 'Tạo hình ảnh tích hợp、Báo cáo chuyên sâu、Báo cáo dữ liệu và các kỹ năng khác，Hỗ trợ tải lên và cài đặt từ xa，「phân tích dự thảo → Xác nhận cài đặt」。',
    tags: ['Tích hợp sẵn', 'tải lên', 'từ xa']
  },
  {
    icon: 'plug',
    title: 'MCP Tích hợp',
    desc: 'Vượt qua Model Context Protocol Giao thức chuẩn để truy cập các dịch vụ công cụ bên ngoài，Thống nhất bắt đầu, dừng và quản lý quyền。',
    tags: ['giao thức chuẩn']
  },
  {
    icon: 'wrench',
    title: 'Công cụ tích hợp',
    desc: 'present_artifacts Giao sản phẩm、Câu hỏi ngắt đang chờ người dùng、Cài đặt kỹ năng theo yêu cầu、Tìm kiếm mạng và nhiều tính năng khác có thể được sử dụng ngay lập tức。',
    tags: ['Sẵn sàng ra khỏi hộp']
  },
  {
    icon: 'fork',
    title: 'chất phụ SubAgents',
    desc: 'Tác nhân chính có thể điều phối các tác nhân phụ bị cô lập，độc lập child thread Thực hiện các nhiệm vụ phức tạp và trả lại sản phẩm。',
    tags: ['dàn nhạc biệt lập']
  },
  {
    icon: 'layers',
    title: 'Điều phối phần mềm trung gian',
    desc: 'Nội dung tìm kiếm cơ sở kiến thức、Xử lý tệp đính kèm、tóm tắt lịch sử offload、Phần mềm trung gian như chèn công cụ động có thể được kết hợp và sắp xếp。',
    tags: ['Có thể kết hợp']
  },
  {
    icon: 'cpu',
    title: 'không đồng bộ Worker',
    desc: 'Dựa trên ARQ nhiệm vụ nền，Thực hiện không đồng bộ các tác vụ tiêu tốn thời gian từ vài phút đến hàng giờ，Hỗ trợ đầu ra hủy và phát trực tuyến。',
    tags: ['nhiệm vụ dài', 'Có thể hủy', 'phát trực tuyến']
  }
]

// cỗ máy tri thức：khả năng chuyển đổi tab，Chuyển phương tiện ở bên phải với các tùy chọn đã chọn
const engineTabs = [
  {
    key: 'parse', icon: 'scan', title: 'Phân tích cú pháp đa định dạng',
    desc: 'MinerU、PaddleX、RapidOCR Phân tích thống nhất PDF、Office、Hình ảnh, v.v. được cấu trúc Markdown。',
    shot: 'https://xerrors.oss-cn-shanghai.aliyuncs.com/github/image-20260605205221908.png'
  },
  {
    key: 'retrieval', icon: 'database', title: 'Agentic RAG',
    desc: 'Tác nhân xác định độc lập thời gian truy xuất và truy vấn，Nhiều vòng truy xuất vector + Rerank，Trả lời với trích dẫn có thể theo dõi。',
    shot: 'https://xerrors.oss-cn-shanghai.aliyuncs.com/github/image-20260604205342546.png'
  },
  {
    key: 'graph', icon: 'share', title: 'Sơ đồ tri thức',
    desc: 'Trích xuất các thực thể và mối quan hệ để xây dựng biểu đồ tri thức，Tăng cường tham gia truy xuất đồ thị con，và hỗ trợ khám phá trực quan。',
    shot: 'https://xerrors.oss-cn-shanghai.aliyuncs.com/github/image-20260604204056298.png'
  },
  {
    key: 'eval', icon: 'chart', title: 'Đánh giá tìm kiếm',
    desc: 'Đánh giá chất lượng tìm kiếm tích hợp，Hỗ trợ các lần chạy được đặt tên và so sánh chỉ báo，Định lượng việc thu hồi và trả lời hiệu quả。',
    shot: 'https://xerrors.oss-cn-shanghai.aliyuncs.com/github/image-20260604210111977.png'
  },
  {
    key: 'sources', icon: 'plug', title: 'Tiếp cận nhiều nguồn kiến thức',
    desc: 'hỗ trợ Dify、Notion、Feishu（Đang quy hoạch）Chờ nguồn tri thức bên ngoài truy cập，Tìm kiếm và trích dẫn thống nhất。',
    shot: 'https://xerrors.oss-cn-shanghai.aliyuncs.com/github/image-20260604205611168.png'
  }
]
const activeEngine = ref(0)
const currentEngine = computed(() => engineTabs[activeEngine.value])

// Tường nhà cung cấp mẫu（vùng chọn ngang，Hai hàng bị lệch và cuộn ngược lại）
const ICON_BASE = 'https://registry.npmmirror.com/@lobehub/icons-static-svg/latest/files/icons'
const providers = [
  { name: 'OpenAI', icon: `${ICON_BASE}/openai.svg` },
  { name: 'DeepSeek', icon: `${ICON_BASE}/deepseek-color.svg` },
  { name: 'Tongyi Qianwen', icon: `${ICON_BASE}/bailian-color.svg` },
  { name: 'Phổ trí tuệ AI', icon: `${ICON_BASE}/zhipu-color.svg` },
  { name: 'Moonshot', icon: `${ICON_BASE}/moonshot.svg` },
  { name: 'MiniMax', icon: `${ICON_BASE}/minimax-color.svg` },
  { name: 'SiliconFlow', icon: `${ICON_BASE}/siliconcloud-color.svg` },
  { name: 'OpenRouter', icon: `${ICON_BASE}/openrouter.svg` },
  { name: 'ModelScope', icon: `${ICON_BASE}/modelscope-color.svg` },
  { name: 'OpenCode', icon: `${ICON_BASE}/opencode.svg` },
  { name: 'Xiaomi MiMo', icon: `${ICON_BASE}/xiaomimimo.svg` }
]
// Thay đổi thứ tự bắt đầu của dòng thứ hai để tạo ra sự sai lệch；Tạo một bản sao của mỗi dòng để lặp liền mạch
const providersTop = [...providers, ...providers]
const providersBottom = (() => {
  const rotated = [...providers.slice(5), ...providers.slice(0, 5)]
  return [...rotated, ...rotated]
})()

// Nguyên tắc làm việc
const steps = [
  { n: '01', title: 'Cấu hình cơ sở', desc: 'Nhà cung cấp mô hình truy cập quản trị viên、Xây dựng cơ sở tri thức và biểu đồ tri thức、Phân chia quyền của người dùng và bộ phận。' },
  { n: '02', title: 'đại lý dàn xếp', desc: 'cho Agent gắn kết Skills、MCP、Tools với các đại lý phụ，Kết hợp các khả năng của phần mềm trung gian cần thiết。' },
  { n: '03', title: 'Truy xuất và lý luận', desc: 'Tích hợp truy xuất vectơ và suy luận biểu đồ tri thức trong hội thoại，Công cụ hộp cát thực hiện các tác vụ thực tế。' },
  { n: '04', title: 'Giao sản phẩm', desc: 'Trả lại câu trả lời có trích dẫn，và có thể được xem trước、Kết quả phân phối thẻ sản phẩm có thể tải xuống。' }
]

// Tổng quan về ảnh chụp màn hình sản phẩm
const shots = [
  { title: 'Bàn làm việc đối thoại', desc: 'lớp học ChatGPT Đối thoại đại lý thông minh và phân phối sản phẩm' },
  { title: 'Cấu hình đại lý', desc: 'gắn kết Skills / MCP / Đại lý phụ và phần mềm trung gian' },
  { title: 'Trực quan hóa biểu đồ tri thức', desc: 'Hiển thị trích xuất mối quan hệ thực thể và truy xuất sơ đồ con' },
  { title: 'Mở rộng đại lý', desc: 'Quản lý thống nhất Skills với MCP dịch vụ' }
]

// Cấp doanh nghiệp
const enterprise = [
  { icon: 'shield', title: 'Nhiều quyền thuê nhà và quyền', desc: 'người dùng / Cách ly cấp khoa，Cơ sở tri thức hỗ trợ toàn cầu、Sở、Chia sẻ ba cấp độ cho những người được chỉ định。' },
  { icon: 'key', title: 'API Key Tích hợp', desc: 'phát hành khóa độc lập，cho các hệ thống bên ngoài API Cách gọi các khả năng của nền tảng một cách an toàn。' },
  { icon: 'rocket', title: 'LITE Khởi động nhẹ', desc: 'make up-lite Bỏ qua sự phụ thuộc nặng nề và khởi động nguội nhanh chóng，Docker Compose Sẵn sàng ra khỏi hộp。' }
]

// Kịch bản ứng dụng
const cases = [
  { title: 'Trợ lý hỏi đáp kiến thức doanh nghiệp', desc: 'Làm cho dữ liệu nội bộ có thể tìm kiếm được、tài sản tri thức hợp lý，Trả lời có trích dẫn nguồn。' },
  { title: 'Báo cáo nghiên cứu khoa học và nghiên cứu ngành', desc: 'Với sự giúp đỡ của deep-reporter Kỹ năng tạo các báo cáo dài phân tích chuyên sâu có cấu trúc。' },
  { title: 'nội bộ AI Cơ sở khả năng', desc: 'Cung cấp khả năng quản lý cho từng hệ thống kinh doanh、Dịch vụ đại lý hợp nhất có thể mở rộng。' }
]

// Phân lớp ngăn xếp công nghệ
const techStack = [
  { group: 'giao diện người dùng', items: ['Vue 3', 'Vite', 'Pinia'] },
  { group: 'phụ trợ', items: ['FastAPI', 'LangGraph', 'ARQ'] },
  { group: 'lưu trữ', items: ['PostgreSQL', 'Redis', 'MinIO', 'Milvus', 'Neo4j'] },
  { group: 'phân tích cú pháp', items: ['MinerU', 'PaddleX', 'RapidOCR'] },
  { group: 'triển khai', items: ['Docker Compose'] }
]

// Lời cảm ơn về nguồn mở
const credits = [
  { name: 'LightRAG', url: 'https://github.com/HKUDS/LightRAG' },
  { name: 'DeepAgents', url: 'https://github.com/langchain-ai/deepagents' },
  { name: 'DeerFlow', url: 'https://github.com/bytedance/deer-flow' },
  { name: 'RAGflow', url: 'https://github.com/infiniflow/ragflow' },
  { name: 'LangGraph', url: 'https://github.com/langchain-ai/langgraph' },
  { name: 'QwenPaw', url: 'https://github.com/agentscope-ai/QwenPaw' }
]

// lucide đường dẫn biểu tượng phong cách（stroke 1.5）
const icons = {
  box: '<path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
  sparkles: '<path d="M9.94 15.5A2 2 0 0 0 8.5 14.06l-6.14-1.58a.5.5 0 0 1 0-.96L8.5 9.94A2 2 0 0 0 9.94 8.5l1.58-6.14a.5.5 0 0 1 .96 0L14.06 8.5A2 2 0 0 0 15.5 9.94l6.14 1.58a.5.5 0 0 1 0 .96L15.5 14.06a2 2 0 0 0-1.44 1.44l-1.58 6.14a.5.5 0 0 1-.96 0z"/>',
  plug: '<path d="M12 22v-5"/><path d="M9 7V2"/><path d="M15 7V2"/><path d="M6 13V8h12v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4Z"/>',
  wrench: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
  fork: '<circle cx="12" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><circle cx="18" cy="6" r="3"/><path d="M18 9v2c0 .6-.4 1-1 1H7c-.6 0-1-.4-1-1V9"/><path d="M12 12v3"/>',
  layers: '<path d="M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
  cpu: '<rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/>',
  database: '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/>',
  share: '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" x2="15.42" y1="13.51" y2="17.49"/><line x1="15.41" x2="8.59" y1="6.51" y2="10.49"/>',
  scan: '<path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/><path d="M7 12h10"/>',
  shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
  key: '<path d="m15.5 7.5 2.3 2.3a1 1 0 0 0 1.4 0l2.1-2.1a1 1 0 0 0 0-1.4L19 4"/><path d="m21 2-9.6 9.6"/><circle cx="7.5" cy="15.5" r="5.5"/>',
  rocket: '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>',
  chart: '<path d="M3 3v18h18"/><path d="M7 16v-5"/><path d="M12 16V8"/><path d="M17 16v-3"/>'
}

// Lệnh nhập cuộn
const vReveal = {
  mounted(el) {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    el.classList.add('reveal')
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (e.isIntersecting) {
          el.classList.add('in-view')
          io.unobserve(el)
        }
      }
    }, { threshold: 0.1 })
    io.observe(el)
  }
}
</script>

<template>
  <div class="yx-home">
    <!-- ===== Hero ===== -->
    <section class="yx-hero">
      <div class="yx-ambient" aria-hidden="true">
        <span class="yx-orb yx-orb--1"></span>
        <span class="yx-orb yx-orb--2"></span>
        <span class="yx-orb yx-orb--3"></span>
        <div class="yx-grid"></div>
      </div>
      <div class="yx-container yx-hero__inner">
        <span class="yx-badge">v0.7.0 · MIT Nguồn mở · LangGraph lái xe</span>
        <h1 class="yx-hero__title">Phân tích ngôn ngữ <span class="yx-accent">Yuxi</span></h1>
        <p class="yx-hero__subtitle">Sự kết hợp RAG Tác nhân thông minh với biểu đồ tri thức Harness nền tảng</p>
        <p class="yx-hero__desc">
          Cơ sở kiến thức cấu hình quản trị viên、Mô hình và quyền，Người dùng trong lớp ChatGPT trong giao diện，
          và có thể gắn được Skills、MCP、Đối thoại đại lý giữa đại lý phụ và công cụ hộp cát，
          Nhận nguồn có trích dẫn、Lập luận về biểu đồ tri thức và các câu trả lời về sản phẩm có thể phân phối được。
        </p>
        <div class="yx-hero__actions">
          <a class="yx-btn yx-btn--primary" :href="withBase('/intro/quick-start')">bắt đầu nhanh</a>
          <a class="yx-btn yx-btn--ghost" :href="GITHUB" target="_blank" rel="noreferrer">trong GitHub Xem</a>
          <a class="yx-btn yx-btn--text" :href="DEMO" target="_blank" rel="noreferrer">▷ Video giới thiệu</a>
        </div>
        <div class="yx-hero__shot">
          <img
            class="yx-hero__img"
            src="https://xerrors.oss-cn-shanghai.aliyuncs.com/github/image-20260608002434299.png"
            alt="Phân tích ngôn ngữ Yuxi Xem trước giao diện sản phẩm"
            loading="lazy"
          />
        </div>
      </div>
    </section>

    <!-- ===== dải dữ liệu ===== -->
    <section class="yx-stats">
      <div class="yx-container yx-stats__inner">
        <div v-for="s in stats" :key="s.label" class="yx-stat">
          <div class="yx-stat__value">{{ s.value }}</div>
          <div class="yx-stat__label">{{ s.label }}</div>
        </div>
      </div>
    </section>

    <!-- ===== Harness trung tâm khả năng ===== -->
    <section class="yx-section">
      <div class="yx-container">
        <header v-reveal class="yx-head">
          <span class="yx-head__eyebrow">Thời gian chạy đại lý</span>
          <h2 class="yx-head__title">Không chỉ là một cuộc trò chuyện，Thực hiện và phân phối tốt hơn</h2>
          <p class="yx-head__sub">Yuxi Tích hợp sẵn một bộ hoàn chỉnh Harness——hộp cát、Kỹ năng、Công cụ、Đại lý phụ và phần mềm trung gian，Hãy để đại lý thực sự hoàn thành nhiệm vụ。</p>
        </header>
        <div class="yx-bento">
          <article
            v-for="cap in capabilities"
            :key="cap.title"
            v-reveal
            class="yx-cap"
            :class="{ 'yx-cap--lg': cap.span }"
          >
            <span class="yx-cap__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" v-html="icons[cap.icon]" />
            </span>
            <h3 class="yx-cap__title">{{ cap.title }}</h3>
            <p class="yx-cap__desc">{{ cap.desc }}</p>
            <div class="yx-cap__tags">
              <span v-for="t in cap.tags" :key="t" class="yx-tag">{{ t }}</span>
            </div>
            <img v-if="cap.shot" class="yx-cap__shot-img" :src="cap.shot" :alt="cap.title" loading="lazy" />
          </article>
        </div>
      </div>
    </section>

    <!-- ===== cỗ máy tri thức ===== -->
    <section class="yx-section yx-section--soft">
      <div class="yx-container yx-split">
        <div v-reveal class="yx-split__text">
          <span class="yx-head__eyebrow">cỗ máy tri thức</span>
          <h2 class="yx-head__title">Từ tài liệu đến tài sản tri thức hợp lý</h2>
          <ul class="yx-tabs">
            <li
              v-for="(t, i) in engineTabs"
              :key="t.key"
              class="yx-tab"
              :class="{ 'yx-tab--active': activeEngine === i }"
              @click="activeEngine = i"
            >
              <span class="yx-list__ic" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" v-html="icons[t.icon]" />
              </span>
              <div class="yx-tab__body">
                <strong>{{ t.title }}</strong>
                <div class="yx-tab__desc"><p>{{ t.desc }}</p></div>
              </div>
            </li>
          </ul>
        </div>
        <div v-reveal class="yx-split__media">
          <div class="yx-engine-media">
            <Transition name="yx-fade" mode="out-in">
              <img
                v-if="currentEngine.shot"
                :key="currentEngine.key"
                class="yx-engine-frame"
                :src="currentEngine.shot"
                :alt="currentEngine.title"
                loading="lazy"
              />
              <div
                v-else
                :key="currentEngine.key"
                class="yx-engine-frame yx-engine-ph"
                role="img"
                :aria-label="currentEngine.title + ' Xem trước'"
              >
                <span>{{ currentEngine.title }} · Xem trước</span>
              </div>
            </Transition>
          </div>
        </div>
      </div>
    </section>

    <!-- ===== Tường nhà cung cấp mẫu ===== -->
    <section class="yx-section">
      <div class="yx-container">
        <header v-reveal class="yx-head">
          <span class="yx-head__eyebrow">nhà cung cấp mô hình</span>
          <h2 class="yx-head__title">Truy cập ở một nơi，Chuyển đổi mọi nơi</h2>
          <p class="yx-head__sub">thống nhất <code>provider_id:model_id</code> Cấu hình，Bao gồm các nhà cung cấp mô hình chính thống，và hỗ trợ tùy biến provider。</p>
        </header>
        <div v-reveal class="yx-marquee">
          <div class="yx-marquee__row">
            <div class="yx-marquee__track">
              <div v-for="(p, i) in providersTop" :key="'t' + i" class="yx-mq-item">
                <img :src="p.icon" :alt="p.name" loading="lazy" />
                <span>{{ p.name }}</span>
              </div>
            </div>
          </div>
          <div class="yx-marquee__row yx-marquee__row--rev">
            <div class="yx-marquee__track">
              <div v-for="(p, i) in providersBottom" :key="'b' + i" class="yx-mq-item">
                <img :src="p.icon" :alt="p.name" loading="lazy" />
                <span>{{ p.name }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ===== Nguyên tắc làm việc ===== -->
    <section class="yx-section yx-section--soft">
      <div class="yx-container">
        <header v-reveal class="yx-head">
          <span class="yx-head__eyebrow">Nguyên tắc làm việc</span>
          <h2 class="yx-head__title">Xây dựng ứng dụng đại lý thông minh của bạn theo bốn bước</h2>
        </header>
        <div class="yx-steps">
          <div v-for="(st, i) in steps" :key="st.n" v-reveal class="yx-step">
            <div class="yx-step__n">{{ st.n }}</div>
            <h3 class="yx-step__title">{{ st.title }}</h3>
            <p class="yx-step__desc">{{ st.desc }}</p>
            <span v-if="i < steps.length - 1" class="yx-step__arrow" aria-hidden="true">→</span>
          </div>
        </div>
      </div>
    </section>

    <!-- ===== Tổng quan về sản phẩm ===== -->
    <section class="yx-section">
      <div class="yx-container">
        <header v-reveal class="yx-head">
          <span class="yx-head__eyebrow">Tổng quan về sản phẩm</span>
          <h2 class="yx-head__title">một bàn làm việc，Bao quát toàn bộ quá trình</h2>
        </header>
        <div class="yx-shots">
          <figure v-for="sh in shots" :key="sh.title" v-reveal class="yx-shot">
            <div class="yx-placeholder" role="img" :aria-label="sh.title + ' Trình giữ chỗ ảnh chụp màn hình'">
              <span>{{ sh.title }} · 16:9</span>
            </div>
            <figcaption>
              <strong>{{ sh.title }}</strong>
              <span>{{ sh.desc }}</span>
            </figcaption>
          </figure>
        </div>
      </div>
    </section>

    <!-- ===== Cấp doanh nghiệp ===== -->
    <section class="yx-section yx-section--soft">
      <div class="yx-container">
        <header v-reveal class="yx-head">
          <span class="yx-head__eyebrow">Cấp doanh nghiệp và có thể tích hợp</span>
          <h2 class="yx-head__title">Từ xác minh nguyên mẫu đến triển khai nhóm</h2>
        </header>
        <div class="yx-cards3">
          <article v-for="e in enterprise" :key="e.title" v-reveal class="yx-card">
            <span class="yx-cap__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" v-html="icons[e.icon]" />
            </span>
            <h3>{{ e.title }}</h3>
            <p>{{ e.desc }}</p>
          </article>
        </div>
      </div>
    </section>

    <!-- ===== Kịch bản ứng dụng ===== -->
    <section class="yx-section">
      <div class="yx-container">
        <header v-reveal class="yx-head">
          <span class="yx-head__eyebrow">Kịch bản ứng dụng</span>
          <h2 class="yx-head__title">Thích ứng với hoạt động kinh doanh thực sự của bạn</h2>
        </header>
        <div class="yx-cards3">
          <article v-for="c in cases" :key="c.title" v-reveal class="yx-card yx-card--case">
            <h3>{{ c.title }}</h3>
            <p>{{ c.desc }}</p>
          </article>
        </div>
      </div>
    </section>

    <!-- ===== ngăn xếp công nghệ ===== -->
    <section class="yx-section yx-section--soft">
      <div class="yx-container">
        <header v-reveal class="yx-head">
          <span class="yx-head__eyebrow">ngăn xếp công nghệ</span>
          <h2 class="yx-head__title">Nền tảng kỹ thuật hiện đại và vững chắc</h2>
        </header>
        <div class="yx-tech">
          <div v-for="t in techStack" :key="t.group" v-reveal class="yx-tech__row">
            <div class="yx-tech__group">{{ t.group }}</div>
            <div class="yx-tech__items">
              <span v-for="it in t.items" :key="it" class="yx-chip">{{ it }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ===== bắt đầu nhanh ===== -->
    <section class="yx-section">
      <div class="yx-container">
        <header v-reveal class="yx-head">
          <span class="yx-head__eyebrow">bắt đầu nhanh</span>
          <h2 class="yx-head__title">Ba bước để bắt đầu chạy cục bộ</h2>
        </header>
        <div v-reveal class="yx-quick">
          <pre class="yx-code"><code><span class="yx-c-cmt"># 1. Sao chép và khởi tạo</span>
git clone --branch v0.7.0 --depth 1 https://github.com/xerrors/Yuxi.git
cd Yuxi && ./scripts/init.sh

<span class="yx-c-cmt"># 2. sử dụng Docker bắt đầu</span>
docker compose up --build

<span class="yx-c-cmt"># 3. Truy cập trình duyệt</span>
open http://localhost:5173</code></pre>
          <p class="yx-quick__tip">Không cần nền tảng kiến thức / Sơ đồ tri thức và các phụ thuộc nặng nề khác，Có sẵn <code>make up-lite</code> để LITE Chế độ nhẹ khởi động nhanh。</p>
        </div>
      </div>
    </section>

    <!-- ===== Người đóng góp & Lời cảm ơn ===== -->
    <section class="yx-section yx-section--soft">
      <div class="yx-container yx-center">
        <header v-reveal class="yx-head">
          <span class="yx-head__eyebrow">cộng đồng</span>
          <h2 class="yx-head__title">Được xây dựng bởi cộng đồng nguồn mở</h2>
        </header>
        <a v-reveal :href="GITHUB + '/graphs/contributors'" target="_blank" rel="noreferrer" class="yx-contrib">
          <img src="https://contrib.rocks/image?repo=xerrors/Yuxi&max=60&columns=12" alt="Yuxi Tường hình đại diện của người đóng góp" loading="lazy" />
        </a>
        <p v-reveal class="yx-credits">
          Đứng trên vai người khổng lồ ——
          <template v-for="(c, i) in credits" :key="c.name">
            <a :href="c.url" target="_blank" rel="noreferrer">{{ c.name }}</a><span v-if="i < credits.length - 1"> · </span>
          </template>
        </p>
      </div>
    </section>

    <!-- ===== cuối cùng CTA ===== -->
    <section class="yx-cta">
      <div class="yx-container yx-cta__inner" v-reveal>
        <h2>Bắt đầu xây dựng đại lý của bạn ngay bây giờ</h2>
        <p>Nguồn mở、Có thể tự lưu trữ、Đối với các tình huống kinh doanh thực tế。</p>
        <div class="yx-hero__actions yx-cta__actions">
          <a class="yx-btn yx-btn--primary" :href="withBase('/intro/quick-start')">bắt đầu nhanh</a>
          <a class="yx-btn yx-btn--ghost" :href="GITHUB" target="_blank" rel="noreferrer">đi tới GitHub ★</a>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.yx-home {
  --yx-max: 1152px;
  --yx-gap: 24px;
  --yx-brand: var(--main-700);
  --yx-brand-hover: var(--main-bright);
  --yx-brand-soft: rgba(4, 106, 130, .12);
  --yx-lime: #c6f43a;
  --yx-lime-strong: #6f9300;
  --yx-lime-soft: rgba(198, 244, 58, .24);
  color: var(--vp-c-text-1);
  font-size: 16px;
  line-height: 1.6;
}
.yx-container {
  max-width: var(--yx-max);
  margin: 0 auto;
  padding: 0 24px;
}
.yx-center { text-align: center; }
.yx-accent { color: var(--yx-brand); }

/* nhịp điệu đoạn văn */
.yx-section { padding: 96px 0; }
.yx-section--soft { background: var(--vp-c-bg-soft); }

/* khối tiêu đề */
.yx-head { max-width: 720px; margin: 0 auto 48px; text-align: center; }
.yx-head__eyebrow {
  display: inline-block;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--yx-brand);
  margin-bottom: 12px;
}
.yx-head__title { font-size: 34px; font-weight: 700; line-height: 1.25; margin: 0; letter-spacing: -.01em; }
.yx-head__sub { margin: 16px auto 0; color: var(--vp-c-text-2); font-size: 17px; }
.yx-head__sub code, .yx-quick__tip code {
  font-size: .85em; padding: 2px 6px; border-radius: 6px;
  background: var(--vp-c-bg-alt); color: var(--yx-brand);
}

/* ===== Hero ===== */
.yx-hero { padding: 88px 0 64px; text-align: center; position: relative; overflow: hidden; }
.yx-hero__inner { position: relative; z-index: 1; }

/* nền khí quyển：quả cầu ánh sáng nổi + lưới mesh */
.yx-ambient { position: absolute; inset: 0; z-index: 0; overflow: hidden; pointer-events: none; }
.yx-orb { position: absolute; border-radius: 50%; filter: blur(70px); will-change: transform; }
.yx-orb--1 {
  width: 460px; height: 460px; top: -180px; right: -80px;
  background: var(--yx-brand-soft); opacity: .6;
  animation: yxOrbFloat 18s ease-in-out infinite;
}
.yx-orb--2 {
  width: 380px; height: 380px; top: -120px; left: -120px;
  background: var(--yx-lime-soft); opacity: .5;
  animation: yxOrbFloat 22s ease-in-out infinite reverse;
}
.yx-orb--3 {
  width: 320px; height: 320px; top: 30px; left: 46%;
  background: var(--yx-brand-soft); opacity: .5;
  animation: yxOrbFloat 26s ease-in-out infinite;
}
.yx-grid {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(to right, var(--vp-c-divider) 1px, transparent 1px),
    linear-gradient(to bottom, var(--vp-c-divider) 1px, transparent 1px);
  background-size: 60px 60px; opacity: .5;
  -webkit-mask-image: radial-gradient(ellipse 75% 60% at 50% 0%, #000, transparent 72%);
  mask-image: radial-gradient(ellipse 75% 60% at 50% 0%, #000, transparent 72%);
}
@keyframes yxOrbFloat {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(0, -26px) scale(1.04); }
}
.yx-badge {
  display: inline-block; font-size: 13px; font-weight: 500;
  padding: 6px 14px; border-radius: 999px;
  border: 1px solid var(--vp-c-divider);
  background: var(--vp-c-bg); color: var(--vp-c-text-2);
  margin-bottom: 24px;
}
.yx-hero__title { font-size: 60px; font-weight: 800; line-height: 1.05; margin: 0; letter-spacing: -.03em; }
.yx-hero__subtitle { font-size: 24px; font-weight: 600; margin: 18px 0 0; color: var(--vp-c-text-1); }
.yx-hero__desc { max-width: 640px; margin: 18px auto 0; color: var(--vp-c-text-2); font-size: 17px; }
.yx-hero__actions { display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; margin-top: 32px; }

/* nút */
.yx-btn {
  display: inline-flex; align-items: center; gap: 6px;
  height: 44px; padding: 0 22px; border-radius: 10px;
  font-size: 15px; font-weight: 600; cursor: pointer;
  transition: transform .2s ease, background-color .2s ease, border-color .2s ease, color .2s ease;
  border: 1px solid transparent; text-decoration: none;
}
.yx-btn--primary { background: var(--yx-brand); color: #fff; }
.yx-btn--primary:hover { background: var(--yx-brand-hover); transform: translateY(-1px); }
.yx-btn--ghost { border-color: var(--vp-c-divider); color: var(--vp-c-text-1); background: var(--vp-c-bg); }
.yx-btn--ghost:hover { border-color: var(--yx-brand); color: var(--yx-brand); }
.yx-btn--text { color: var(--vp-c-text-2); }
.yx-btn--text:hover { color: var(--yx-brand); }

.yx-hero__shot { margin-top: 56px; }
.yx-hero__img {
  display: block; width: 100%; border-radius: 14px;
  border: 1px solid var(--vp-c-divider);
  box-shadow: 0 24px 60px -28px rgba(0, 0, 0, .25);
}

/* hình ảnh giữ chỗ */
.yx-placeholder {
  aspect-ratio: 16 / 9; width: 100%;
  display: flex; align-items: center; justify-content: center;
  border: 1px dashed var(--vp-c-divider); border-radius: 14px;
  background:
    linear-gradient(var(--vp-c-bg-soft), var(--vp-c-bg-soft)) padding-box,
    var(--vp-c-bg);
  color: var(--vp-c-text-3); font-size: 14px; letter-spacing: .02em;
}
.yx-placeholder--hero {
  border-style: solid;
  box-shadow: 0 24px 60px -28px rgba(0, 0, 0, .25);
}

/* ===== dải dữ liệu ===== */
.yx-stats { border-top: 1px solid var(--vp-c-divider); border-bottom: 1px solid var(--vp-c-divider); }
.yx-stats__inner { display: grid; grid-template-columns: repeat(4, 1fr); }
.yx-stat { text-align: center; padding: 32px 16px; }
.yx-stat + .yx-stat { border-left: 1px solid var(--vp-c-divider); }
.yx-stat__value {
  font-size: 36px; font-weight: 800; color: var(--yx-brand);
  font-variant-numeric: tabular-nums; letter-spacing: -.02em;
}
.yx-stat__label { margin-top: 6px; font-size: 14px; color: var(--vp-c-text-2); }

/* ===== Bento ===== */
.yx-bento {
  display: grid; gap: var(--yx-gap);
  grid-template-columns: repeat(3, 1fr);
}
.yx-cap {
  border: 1px solid var(--vp-c-divider); border-radius: 16px;
  padding: 28px; background: var(--vp-c-bg);
  transition: transform .2s ease, border-color .2s ease;
}
.yx-cap:hover { transform: translateY(-3px); border-color: var(--yx-brand); }
.yx-cap--lg { grid-column: span 1; grid-row: span 2; display: flex; flex-direction: column; }
.yx-cap__icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 44px; height: 44px; border-radius: 12px;
  background: var(--yx-brand-soft); color: var(--yx-brand);
  margin-bottom: 18px;
}
.yx-cap__icon svg { width: 22px; height: 22px; }
.yx-cap__title { font-size: 18px; font-weight: 700; margin: 0 0 8px; }
.yx-cap__desc { color: var(--vp-c-text-2); font-size: 14.5px; margin: 0; }
.yx-cap__tags { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
.yx-tag {
  font-size: 12px; padding: 3px 10px; border-radius: 999px;
  background: var(--vp-c-bg-soft); border: 1px solid var(--vp-c-divider);
  color: var(--vp-c-text-2);
}
.yx-cap__shot-img {
  display: block; width: 100%; margin-top: 20px;
  border-radius: 12px; border: 1px solid var(--vp-c-divider);
}

/* ===== Split（cỗ máy tri thức）===== */
.yx-split { display: grid; grid-template-columns: 0.82fr 1.18fr; gap: 48px; align-items: start; }
.yx-split .yx-head__eyebrow { display: inline-block; }
.yx-split .yx-head__title { text-align: left; font-size: 30px; }
.yx-tabs { list-style: none; margin: 28px 0 0; padding: 0; display: grid; gap: 8px; }
.yx-tab {
  display: flex; align-items: center; gap: 14px; padding: 12px 14px;
  border-radius: 12px; border: 1px solid transparent; cursor: pointer;
  transition: background-color .2s ease, border-color .2s ease;
}
.yx-tab:hover { background: var(--vp-c-bg); }
.yx-tab--active { background: var(--vp-c-bg); border-color: var(--vp-c-divider); }
.yx-tab .yx-list__ic { opacity: .55; transition: opacity .2s ease; }
.yx-tab--active .yx-list__ic { opacity: 1; }
.yx-list__ic {
  flex: none; width: 38px; height: 38px; border-radius: 10px;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--yx-brand-soft); color: var(--yx-brand);
}
.yx-list__ic svg { width: 20px; height: 20px; }
.yx-tab--active .yx-list__ic { background: var(--yx-lime-soft); color: var(--yx-lime-strong); }
.yx-tab__body { min-width: 0; }
.yx-tab strong { display: block; font-size: 16px; }
.yx-tab__desc {
  display: grid; grid-template-rows: 0fr;
  transition: grid-template-rows .25s ease;
}
.yx-tab--active .yx-tab__desc { grid-template-rows: 1fr; }
.yx-tab__desc p {
  overflow: hidden; margin: 0; color: var(--vp-c-text-2); font-size: 14px; line-height: 1.55;
}
.yx-tab--active .yx-tab__desc p { margin-top: 4px; }

/* Khu vực truyền thông Công cụ Tri thức（4:3，Theo dõi tab chuyển đổi） */
.yx-engine-media {
  position: relative; width: 100%; aspect-ratio: 4 / 3; margin-top: 40px;
  border-radius: 14px; overflow: hidden; border: 1px solid var(--vp-c-divider);
}
.yx-engine-frame { position: absolute; inset: 0; width: 100%; height: 100%; display: block; }
img.yx-engine-frame { object-fit: cover; }
.yx-engine-ph {
  display: flex; align-items: center; justify-content: center;
  background: var(--vp-c-bg-soft); color: var(--vp-c-text-3);
  font-size: 14px; letter-spacing: .02em;
}
.yx-fade-enter-active, .yx-fade-leave-active { transition: opacity .25s ease; }
.yx-fade-enter-from, .yx-fade-leave-to { opacity: 0; }

/* ===== Tường nhà cung cấp mẫu（vùng chọn）===== */
.yx-marquee {
  display: flex; flex-direction: column; gap: 18px;
  -webkit-mask-image: linear-gradient(90deg, transparent, #000 8%, #000 92%, transparent);
  mask-image: linear-gradient(90deg, transparent, #000 8%, #000 92%, transparent);
}
.yx-marquee__row { display: flex; overflow: hidden; }
.yx-marquee__track {
  display: flex; gap: 16px; flex: none; width: max-content;
  padding-right: 16px;
  animation: yxMarquee 42s linear infinite;
}
.yx-marquee__row--rev .yx-marquee__track { animation-direction: reverse; }
.yx-marquee:hover .yx-marquee__track { animation-play-state: paused; }
.yx-mq-item {
  display: flex; align-items: center; gap: 10px; flex: none;
  padding: 10px 20px; border-radius: 999px;
  border: 1px solid var(--vp-c-divider); background: var(--vp-c-bg);
  white-space: nowrap;
}
.yx-mq-item img { width: 24px; height: 24px; object-fit: contain; flex: none; }
.yx-mq-item span { font-weight: 600; font-size: 15px; color: var(--vp-c-text-1); }
@keyframes yxMarquee {
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
}

/* ===== Nguyên tắc làm việc ===== */
.yx-steps { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--yx-gap); }
.yx-step { position: relative; padding: 28px 24px; border: 1px solid var(--vp-c-divider); border-radius: 16px; background: var(--vp-c-bg); }
.yx-step__n { font-size: 26px; font-weight: 800; color: var(--yx-brand); font-variant-numeric: tabular-nums; }
.yx-step__title { font-size: 17px; font-weight: 700; margin: 10px 0 8px; }
.yx-step__desc { margin: 0; color: var(--vp-c-text-2); font-size: 14px; }
.yx-step__arrow {
  position: absolute; right: -16px; top: 50%; transform: translateY(-50%);
  color: var(--vp-c-text-3); font-size: 18px; z-index: 1;
}

/* ===== Tổng quan về sản phẩm ===== */
.yx-shots { display: grid; grid-template-columns: repeat(2, 1fr); gap: 32px; }
.yx-shot { margin: 0; }
.yx-shot figcaption { margin-top: 14px; }
.yx-shot figcaption strong { font-size: 16px; }
.yx-shot figcaption span { display: block; color: var(--vp-c-text-2); font-size: 14px; margin-top: 2px; }

/* ===== Ba thẻ（Cấp doanh nghiệp / bối cảnh）===== */
.yx-cards3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--yx-gap); }
.yx-card {
  border: 1px solid var(--vp-c-divider); border-radius: 16px;
  padding: 28px; background: var(--vp-c-bg);
  transition: transform .2s ease, border-color .2s ease;
}
.yx-card:hover { transform: translateY(-3px); border-color: var(--yx-brand); }
.yx-card h3 { font-size: 18px; font-weight: 700; margin: 0 0 8px; }
.yx-card p { margin: 0; color: var(--vp-c-text-2); font-size: 14.5px; }
.yx-card--case { border-left: 3px solid var(--yx-lime); }

/* ===== ngăn xếp công nghệ ===== */
.yx-tech { max-width: 860px; margin: 0 auto; }
.yx-tech__row { display: grid; grid-template-columns: 100px 1fr; gap: 24px; align-items: center; padding: 18px 0; }
.yx-tech__row + .yx-tech__row { border-top: 1px solid var(--vp-c-divider); }
.yx-tech__group { font-weight: 600; color: var(--vp-c-text-2); font-size: 14px; }
.yx-tech__items { display: flex; flex-wrap: wrap; gap: 10px; }
.yx-chip {
  font-size: 14px; font-weight: 500; padding: 6px 14px; border-radius: 8px;
  background: var(--vp-c-bg-soft); border: 1px solid var(--vp-c-divider);
}

/* ===== bắt đầu nhanh ===== */
.yx-quick { max-width: 760px; margin: 0 auto; }
.yx-code {
  margin: 0; padding: 24px; border-radius: 14px;
  background: #1b1b1f;
  border: 1px solid var(--vp-c-divider);
  overflow-x: auto; font-size: 14px; line-height: 1.8;
  font-family: var(--vp-font-family-mono);
  color: #e6e6e6;
}
.yx-c-cmt { color: #6a9955; }
.yx-quick__tip { margin: 18px 0 0; text-align: center; color: var(--vp-c-text-2); font-size: 14px; }

/* ===== cộng đồng ===== */
.yx-contrib { display: block; max-width: 720px; margin: 0 auto; }
.yx-contrib img { width: 100%; border-radius: 12px; }
.yx-credits { margin: 32px 0 0; color: var(--vp-c-text-2); font-size: 14.5px; }
.yx-credits a { color: var(--yx-brand); text-decoration: none; }
.yx-credits a:hover { text-decoration: underline; }

/* ===== cuối cùng CTA ===== */
.yx-cta { padding: 96px 0; text-align: center; border-top: 1px solid var(--vp-c-divider); }
.yx-cta__inner h2 { font-size: 34px; font-weight: 800; margin: 0; letter-spacing: -.01em; }
.yx-cta__inner p { margin: 14px 0 0; color: var(--vp-c-text-2); font-size: 17px; }
.yx-cta__actions { margin-top: 28px; }

/* ===== Hoạt ảnh nhập cảnh ===== */
.reveal { opacity: 0; transform: translateY(18px); transition: opacity .6s ease, transform .6s ease; }
.reveal.in-view { opacity: 1; transform: none; }

/* ===== đáp ứng ===== */
@media (max-width: 1024px) {
  .yx-bento { grid-template-columns: repeat(2, 1fr); }
  .yx-cap--lg { grid-column: span 2; grid-row: auto; }
}
@media (max-width: 768px) {
  .yx-section, .yx-hero, .yx-cta { padding: 64px 0; }
  .yx-hero { padding-top: 64px; }
  .yx-hero__title { font-size: 44px; }
  .yx-hero__subtitle { font-size: 20px; }
  .yx-head__title { font-size: 28px; }
  .yx-bento, .yx-cards3, .yx-steps, .yx-shots { grid-template-columns: 1fr; }
  .yx-cap--lg { grid-column: auto; }
  .yx-split { grid-template-columns: 1fr; gap: 32px; }
  .yx-split .yx-head__title { text-align: center; }
  .yx-split__text { text-align: center; }
  .yx-tab { text-align: left; }
  .yx-stats__inner { grid-template-columns: repeat(2, 1fr); }
  .yx-stat:nth-child(3) { border-left: none; }
  .yx-stat:nth-child(odd) { border-left: none; }
  .yx-stat:nth-child(even) { border-left: 1px solid var(--vp-c-divider); }
  .yx-stat:nth-child(n+3) { border-top: 1px solid var(--vp-c-divider); }
  .yx-step__arrow { display: none; }
}
@media (prefers-reduced-motion: reduce) {
  .reveal { opacity: 1; transform: none; transition: none; }
  .yx-btn:hover, .yx-cap:hover, .yx-card:hover, .yx-provider:hover { transform: none; }
  .yx-orb, .yx-marquee__track { animation: none; }
}
</style>
