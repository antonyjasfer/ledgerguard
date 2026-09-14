/** Safe monetary and number formatting helpers */
export function formatMoney(val: unknown, fallback: string = '0.00'): string {
  if (val === null || val === undefined || val === '') return fallback;
  if (typeof val === 'object' && val !== null) {
    const values = Object.values(val);
    if (values.length > 0) return formatMoney(values[0], fallback);
    return fallback;
  }
  const num = typeof val === 'number' ? val : parseFloat(String(val));
  return isNaN(num) ? fallback : num.toFixed(2);
}

export function formatNumber(val: unknown, decimals: number = 2, fallback: string = '--'): string {
  if (val === null || val === undefined || val === '') return fallback;
  if (typeof val === 'object' && val !== null) {
    const values = Object.values(val);
    if (values.length > 0) return formatNumber(values[0], decimals, fallback);
    return fallback;
  }
  const num = typeof val === 'number' ? val : parseFloat(String(val));
  return isNaN(num) ? fallback : num.toFixed(decimals);
}
