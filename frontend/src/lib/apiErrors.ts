// DRF 400 bodies map field name to a message or a list of messages; keep the first of each.
export function fieldErrors(err: unknown): Record<string, string> {
  const response = (err as { response?: { status?: number; data?: unknown } } | null)?.response;
  const data = response?.data;
  if (response?.status !== 400 || typeof data !== 'object' || data === null || Array.isArray(data)) {
    return {};
  }
  const result: Record<string, string> = {};
  for (const [field, value] of Object.entries(data)) {
    const first = Array.isArray(value) ? value[0] : value;
    if (typeof first === 'string') result[field] = first;
  }
  return result;
}
