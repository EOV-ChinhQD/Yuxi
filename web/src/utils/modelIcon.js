const ICON_BASE = 'https://registry.npmmirror.com/@lobehub/icons-static-svg/latest/files/icons'
const WHITE_ICON_FILTER = 'brightness(0) invert(1)'

// PORT-CONFLICT: giữ cả hai API — modelIcons (bản fork, dùng bởi ProviderCatalogModal)
// và modelAvatars (upstream, dùng bởi ModelProviderManagePanel)
export const modelIcons = {
  default: `${ICON_BASE}/default.svg`,
  alibaba: `${ICON_BASE}/bailian-color.svg`,
  'alibaba-coding-plan': `${ICON_BASE}/alibabacloud-color.svg`,
  'alibaba-coding-plan-cn': `${ICON_BASE}/alibabacloud-color.svg`,
  anthropic: `${ICON_BASE}/anthropic.svg`,
  ark: `${ICON_BASE}/volcengine-color.svg`,
  dashscope: `${ICON_BASE}/bailian-color.svg`,
  deepseek: `${ICON_BASE}/deepseek-color.svg`,
  google: `${ICON_BASE}/google-color.svg`,
  minimax: `${ICON_BASE}/minimax-color.svg`,
  'minimax-cn': `${ICON_BASE}/minimax-color.svg`,
  modelscope: `${ICON_BASE}/modelscope-color.svg`,
  moonshotai: `${ICON_BASE}/moonshot.svg`,
  'moonshotai-cn': `${ICON_BASE}/moonshot.svg`,
  opencode: `${ICON_BASE}/opencode.svg`,
  openai: `${ICON_BASE}/openai.svg`,
  nvidia: `${ICON_BASE}/nvidia.svg`,
  openrouter: `${ICON_BASE}/openrouter.svg`,
  siliconflow: `${ICON_BASE}/siliconcloud-color.svg`,
  'siliconflow-cn': `${ICON_BASE}/siliconcloud-color.svg`,
  together: `${ICON_BASE}/together-color.svg`,
  'kimi-for-coding': `${ICON_BASE}/moonshot.svg`,
  xiaomi: `${ICON_BASE}/xiaomimimo.svg`,
  'xiaomi-token-plan-cn': `${ICON_BASE}/xiaomimimo.svg`,
  zai: `${ICON_BASE}/zai.svg`,
  'zai-coding-plan': `${ICON_BASE}/zai.svg`,
  zhipu: `${ICON_BASE}/zhipu-color.svg`,
  zhipuai: `${ICON_BASE}/zhipu-color.svg`,
  'zhipuai-coding-plan': `${ICON_BASE}/zhipu-color.svg`
}

const avatar = (icon, background, scale = 0.75, filter = WHITE_ICON_FILTER) => ({
  icon: `${ICON_BASE}/${icon}.svg`,
  background,
  scale,
  filter
})

export const modelAvatars = {
  default: avatar('default', 'var(--gray-100)', 0.72, 'none'),
  alibaba: avatar('alibaba', '#ff6003', 0.8),
  'alibaba-cn': avatar('bailian-color', '#fff', 0.75, 'none'),
  'alibaba-coding-plan': avatar('alibabacloud', '#ff6a00', 0.7),
  'alibaba-coding-plan-cn': avatar('alibabacloud', '#ff6a00', 0.7),
  anthropic: avatar('anthropic', '#f1f0e8', 0.75, 'none'),
  ark: avatar('volcengine-color', '#fff', 0.75, 'none'),
  dashscope: avatar('bailian-color', '#fff', 0.75, 'none'),
  deepseek: avatar('deepseek', '#4d6bfe'),
  google: avatar('google-color', '#fff', 0.75, 'none'),
  minimax: avatar('minimax', 'linear-gradient(to right, #e2167e, #fe603c)'),
  'minimax-cn': avatar('minimax', 'linear-gradient(to right, #e2167e, #fe603c)'),
  modelscope: avatar('modelscope', '#624aff'),
  moonshotai: avatar('moonshot', '#16191e'),
  'moonshotai-cn': avatar('moonshot', '#16191e'),
  opencode: avatar('opencode', '#000'),
  'opencode-go': avatar('opencode', '#000'),
  openai: avatar('openai', '#000'),
  openrouter: avatar(
    'openrouter',
    '#000',
    0.75,
    'brightness(0) saturate(100%) invert(94%) sepia(94%) saturate(1636%) hue-rotate(24deg) brightness(105%) contrast(106%)'
  ),
  siliconflow: avatar('siliconcloud', '#6e29f6', 0.7),
  'siliconflow-cn': avatar('siliconcloud', '#6e29f6', 0.7),
  together: avatar('together', '#fff', 0.75, 'none'),
  'kimi-for-coding': avatar('moonshot', '#16191e'),
  xiaomi: avatar('xiaomimimo', '#000', 0.7),
  'xiaomi-token-plan-cn': avatar('xiaomimimo', '#000', 0.7),
  zai: avatar('zai', '#000', 0.6),
  'zai-coding-plan': avatar('zai', '#000', 0.6),
  zhipu: avatar('zhipu', '#3859ff'),
  zhipuai: avatar('zhipu', '#3859ff'),
  'zhipuai-coding-plan': avatar('zhipu', '#3859ff')
}
