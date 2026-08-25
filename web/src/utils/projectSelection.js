export const AUTO_PROJECT_ID = '__auto__'

export const filterProjects = (projects, query = '') => {
  const keyword = String(query).trim().toLocaleLowerCase()
  if (!keyword) return projects
  return projects.filter((project) => project.name.toLocaleLowerCase().includes(keyword))
}

export const formatRelativeTime = (value, now = Date.now()) => {
  const timestamp = Date.parse(value)
  if (!Number.isFinite(timestamp)) return ''

  const elapsed = Math.max(0, Number(now) - timestamp)
  const minute = 60 * 1000
  const hour = 60 * minute
  const day = 24 * hour
  if (elapsed < minute) return 'just now'
  if (elapsed < hour) return `${Math.floor(elapsed / minute)}m ago`
  if (elapsed < day) return `${Math.floor(elapsed / hour)}h ago`
  if (elapsed < 30 * day) return `${Math.floor(elapsed / day)}d ago`
  if (elapsed < 365 * day) return `${Math.floor(elapsed / (30 * day))}mo ago`
  return `${Math.floor(elapsed / (365 * day))}y ago`
}
