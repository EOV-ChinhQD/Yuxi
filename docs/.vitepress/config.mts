import { defineConfig } from 'vitepress'
import markdownItTaskCheckbox from 'markdown-it-task-checkbox'


// https://vitepress.dev/reference/site-config
export default defineConfig({
  lang: 'en-US',
  title: "Yuxi",
  description: "Yuxi Intelligent Knowledge Base & Multi-Agent RAG Platform",
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
      { text: 'Quick Start', link: '/intro/quick-start' },
      { text: 'Agent Development', link: '/agents/agents-config' }
    ],

    sidebar: [
      {
        text: 'Introduction',
        items: [
          { text: 'What is Yuxi?', link: '/intro/project-overview' },
          { text: 'Quick Start', link: '/intro/quick-start' },
          { text: 'CLI Tool', link: '/intro/cli' },
          { text: 'Model Configuration', link: '/intro/model-config' },
          { text: 'Knowledge Base & Graph', link: '/intro/knowledge-base' },
          { text: 'KB Evaluation', link: '/intro/evaluation' }
        ]
      },
      {
        text: 'Agent Development',
        items: [
          { text: 'Agent Configuration', link: '/agents/agents-config' },
          { text: 'Tools System', link: '/agents/tools-system' },
          { text: 'Middleware', link: '/agents/middleware' },
          { text: 'Agent Evaluation', link: '/agents/agent-evaluation' },
          { text: 'Sandbox Architecture', link: '/agents/sandbox-architecture' },
          { text: 'MCP Integration', link: '/agents/mcp-integration' },
          { text: 'Skills Management', link: '/agents/skills-management' },
          { text: 'Subagents', link: '/agents/subagents-management' }
        ]
      },
      {
        text: 'Advanced Configuration',
        items: [
          { text: 'Configuration System', link: '/advanced/configuration' },
          { text: 'Langfuse Integration', link: '/advanced/langfuse-integration' },
          { text: 'Document Processing', link: '/advanced/document-processing' },
          { text: 'Branding Customization', link: '/advanced/branding' },
          { text: 'Miscellaneous', link: '/advanced/misc' },
          { text: 'Production Deployment', link: '/advanced/deployment' },
          { text: 'API Key Integration', link: '/advanced/api-key-integration' }
        ]
      },
      {
        text: 'Development Guides',
        items: [
          { text: 'Contributing', link: '/develop-guides/contributing' },
          { text: 'Roadmap', link: '/develop-guides/roadmap' },
          { text: 'Changelog', link: '/develop-guides/changelog' },
          { text: 'UI Design Guidelines', link: '/develop-guides/design' },
          { text: 'Testing Guidelines', link: '/develop-guides/testing-guidelines' },
        ]
      }
    ],

    socialLinks: [
      { icon: 'github', link: 'https://github.com/xerrors/Yuxi' }
    ],

    footer: {
      message: 'Released under the MIT License.',
      copyright: 'Copyright © 2025-present Yuxi'
    },

    editLink: {
      pattern: 'https://github.com/xerrors/Yuxi/edit/main/docs/:path',
      text: 'Edit this page on GitHub'
    },

    lastUpdated: {
      text: 'Last Updated',
      formatOptions: {
        dateStyle: 'full',
        timeStyle: 'medium'
      }
    },

    search: {
      provider: 'local',
      options: {
        translations: {
          button: {
            buttonText: 'Search Documentation',
            buttonAriaLabel: 'Search Documentation'
          },
          modal: {
            noResultsText: 'No results found',
            resetButtonTitle: 'Clear query',
            footer: {
              selectText: 'Select',
              navigateText: 'Navigate',
              closeText: 'Close'
            }
          }
        }
      }
    }
  }
})
