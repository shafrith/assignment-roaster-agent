import axios from 'axios';
import type { ErrorResponse } from '../types';

export const API_BASE_URL = `${import.meta.env.VITE_API_URL ?? ''}/api/v1`;

/** No auth: every endpoint the app uses is anonymous. */
export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

const FALLBACK_MESSAGE = 'Edho thappa pochu machan, konjam apram try pannu 🙏';

function isErrorResponse(value: unknown): value is ErrorResponse {
  return (
    typeof value === 'object' &&
    value !== null &&
    'detail' in value &&
    typeof (value as { detail: unknown }).detail === 'string'
  );
}

interface ValidationErrorResponse {
  detail: { msg: string }[];
}

function isValidationErrorResponse(value: unknown): value is ValidationErrorResponse {
  if (typeof value !== 'object' || value === null || !('detail' in value)) return false;
  const detail: unknown = (value as { detail: unknown }).detail;
  return (
    Array.isArray(detail) &&
    detail.every((d: unknown) => typeof d === 'object' && d !== null && typeof (d as { msg?: unknown }).msg === 'string')
  );
}

/** Extract a user-facing message (backend `detail`) from any thrown value. */
export function getErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const data: unknown = err.response?.data;
    if (isErrorResponse(data)) {
      return data.detail;
    }
    if (isValidationErrorResponse(data) && data.detail.length > 0) {
      return data.detail[0].msg;
    }
    if (!err.response) {
      return 'Server-a reach panna mudiyala, network check pannu 📡';
    }
    return FALLBACK_MESSAGE;
  }
  if (err instanceof Error && err.message) {
    return err.message;
  }
  return FALLBACK_MESSAGE;
}

export default api;
