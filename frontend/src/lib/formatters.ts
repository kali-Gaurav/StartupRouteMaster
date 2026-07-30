/**
 * Native Browser Formatters (Suggestion #14)
 * Uses built-in Intl API to avoid heavy date/number libraries.
 */

export const formatDate = (date: Date | string) => {
  const d = typeof date === 'string' ? new Date(date) : date;
  return new Intl.DateTimeFormat('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric'
  }).format(d);
};

export const formatCurrency = (amount: number) => {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0
  }).format(amount);
};

export const formatTime = (timeStr: string) => {
  // '14:30:00' -> '2:30 PM'
  const [h, m] = timeStr.split(':');
  const d = new Date();
  d.setHours(parseInt(h), parseInt(m));
  return new Intl.DateTimeFormat('en-IN', {
    hour: 'numeric',
    minute: 'numeric',
    hour12: true
  }).format(d);
};
