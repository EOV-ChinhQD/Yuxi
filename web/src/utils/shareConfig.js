export function getShareConfigLabel(shareConfig) {
  const config = shareConfig || {}
  const readScope = config.version === 2 ? config.read_scope : config
  const manageScope = config.manage_scope
  if (config.version === 2 && !config.read_scope && !manageScope) return 'Owner only'
  const scopeLabel = (scope) => {
    if (!scope) return 'None'
    if (scope.access_level === 'global') return 'Global'
    if (scope.access_level === 'department') return `Dept(${scope.department_ids?.length || 0})`
    return `User(${scope.user_uids?.length || 0})`
  }
  return manageScope
    ? `Read: ${scopeLabel(readScope)} · Manage: ${scopeLabel(manageScope)}`
    : `Read: ${scopeLabel(readScope)}`
}
