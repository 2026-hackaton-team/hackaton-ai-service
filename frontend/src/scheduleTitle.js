const SYNTHETIC_PREFIX = /^\[합성 (?:시연|예정)\]\s*/

export function isSyntheticScheduleTitle(title) {
  return typeof title === 'string' && SYNTHETIC_PREFIX.test(title)
}

export function displayScheduleTitle(title) {
  return typeof title === 'string' ? title.replace(SYNTHETIC_PREFIX, '') : title
}
