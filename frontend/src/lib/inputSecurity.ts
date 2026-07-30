/**
 * Input sanitization for request safety and consistent handling.
 * Use with Zod for validation; use these for trim/maxLength before sending to API.
 */

const DEFAULT_MAX_LENGTH = 500;

/**
 * Trim and limit length for string inputs. Use for free-text before validation/API.
 * Prevents oversized payloads and accidental leading/trailing whitespace.
 */
export function sanitizeString(
  value: unknown,
  maxLength: number = DEFAULT_MAX_LENGTH
): string {
  if (value == null) return "";
  const s = String(value).trim();
  return s.length > maxLength ? s.slice(0, maxLength) : s;
}

/**
 * Sanitize for display only (e.g. in placeholders). Never use for rendering raw HTML.
 * For HTML use a sanitizer like DOMPurify; prefer text content.
 */
export function sanitizeForDisplay(value: unknown, maxLength = 200): string {
  return sanitizeString(value, maxLength);
}
