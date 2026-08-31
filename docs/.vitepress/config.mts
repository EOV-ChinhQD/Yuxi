import { defineConfig } from 'vitepress'
import markdownItTaskCheckbox from 'markdown-it-task-checkbox'


// https://vitepress.dev/reference/site-config
export default defineConfig({
  lang: 'vi',
  title: "Yuxi",
  description: "Yuxi — Nền tảng RAG mô-đun mở",
  base: '/Yuxi/',
  ignoreDeadLinks: [
    /localhost/,
    /CONTRIBUTING$/,
    /docker-compose\.yml$/,
    /^\.\/intro\//
  ],
  markdown: {
    config: (md) => {
      md.use(markdownItTaskCheckbox)
    }
  },
  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    logo: "/favicon.svg",
    nav: [
      { text: 'Bắt đầu', link: '/intro/quick-start' },
      { text: 'Phát triển Agent', link: '/agents/agents-config' }
    ],

    sidebar: [
      {
        text: 'Giới thiệu',
        items: [
          { text: 'Yuxi là gì?', link: '/intro/project-overview' },
          { text: 'Bắt đầu nhanh', link: '/intro/quick-start' },
          { text: 'CLI', link: '/intro/cli' },
          { text: 'Cấu hình Model', link: '/intro/model-config' },
          { text: 'Knowledge Base & Graph', link: '/intro/knowledge-base' },
          { text: 'Đánh giá', link: '/intro/evaluation' }
        ]
      },
      {
        text: 'Phát triển Agent',
        items: [
          { text: 'Cấu hình Agent', link: '/agents/agents-config' },
          { text: 'Hàng đợi yêu cầu', link: '/agents/agent-request-queue' },
          { text: 'Project & Workdir', link: '/agents/project-workdir' },
          { text: 'Hệ thống Tool', link: '/agents/tools-system' },
          { text: 'Middleware', link: '/agents/middleware' },
          { text: 'Đánh giá Agent', link: '/agents/agent-evaluation' },
          { text: 'Kiến trúc Sandbox', link: '/agents/sandbox-architecture' },
          { text: 'Tích hợp MCP', link: '/agents/mcp-integration' },
          { text: 'Quản lý Skills', link: '/agents/skills-management' },
          { text: 'SubAgents', link: '/agents/subagents-management' }
        ]
      },
      {
        text: 'Cấu hình nâng cao',
        items: [
          { text: 'Hệ thống cấu hình', link: '/advanced/configuration' },
          { text: 'Tích hợp Langfuse', link: '/advanced/langfuse-integration' },
          { text: 'Xử lý tài liệu', link: '/advanced/document-processing' },
          { text: 'Tùy biến thương hiệu', link: '/advanced/branding' },
          { text: 'Khác', link: '/advanced/misc' },
          { text: 'Triển khai Production', link: '/advanced/deployment' },
          { text: 'Tích hợp API Key', link: '/advanced/api-key-integration' }
        ]
      },
      {
        text: 'Hướng dẫn phát triển',
        items: [
          { text: 'Đóng góp', link: '/develop-guides/contributing' },
          { text: 'Roadmap', link: '/develop-guides/roadmap' },
          { text: 'Changelog', link: '/develop-guides/changelog' },
          { text: 'Quy chuẩn thiết kế', link: '/develop-guides/design' },
          { text: 'Quy chuẩn kiểm thử', link: '/develop-guides/testing-guidelines' },
        ]
      }
    ],

    socialLinks: [
      { icon: 'github', link: 'https://github.com/xerrors/Yuxi' }
    ],

    footer: {
      message: 'Phát hành dưới giấy phép MIT — hoan nghênh đóng góp.',
      copyright: 'Copyright © 2025-present Yuxi'
    },

    editLink: {
      pattern: 'https://github.com/EOV-ChinhQD/Yuxi/edit/main/docs/:path',
      text: 'Chỉnh sửa trang này trên GitHub'
    },

    lastUpdated: {
      text: 'Cập nhật lần cuối',
      formatOptions: {
        dateStyle: 'full',
        timeStyle: 'medium'
      }
    },

    search: {
      provider: 'local'
    },

    docFooter: {
      prev: 'Trang trước',
      next: 'Trang sau'
    }
  },
})
