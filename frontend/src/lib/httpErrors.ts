import axios from 'axios';

export function getHttpStatus(error: unknown): number | undefined {
  return axios.isAxiosError(error) ? error.response?.status : undefined;
}

export function isNotFoundError(error: unknown): boolean {
  return getHttpStatus(error) === 404;
}
