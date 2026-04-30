export function formatDate(date) {
  return new Date(date).toLocaleString();
}

export function formatTime(seconds) {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  return `${Math.floor(seconds / 3600)}h`;
}

export function truncateText(text, maxLength = 100) {
  return text.length > maxLength ? `${text.substring(0, maxLength)}...` : text;
}

export function getInitials(name) {
  return name
    .split(' ')
    .map((word) => word[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}
