import type { Paginated, SubmissionListItem, SubmissionResponse } from '../types/api';
import { api } from './api';

export interface CreateSubmissionRequest {
  repoUrl: string;
}

export interface UpdateVisibilityRequest {
  isPublic: boolean;
}

export const DEFAULT_PAGE_SIZE = 10;

export const submissionKeys = {
  all: ['submissions'] as const,
  lists: () => [...submissionKeys.all, 'list'] as const,
  list: (page: number, pageSize: number) => [...submissionKeys.lists(), { page, pageSize }] as const,
  details: () => [...submissionKeys.all, 'detail'] as const,
  detail: (id: number) => [...submissionKeys.details(), id] as const,
};

export const submissionService = {
  async create(payload: CreateSubmissionRequest): Promise<SubmissionResponse> {
    const { data } = await api.post<SubmissionResponse>('/submissions', payload);
    return data;
  },

  async list(page: number, pageSize: number = DEFAULT_PAGE_SIZE): Promise<Paginated<SubmissionListItem>> {
    const { data } = await api.get<Paginated<SubmissionListItem>>('/submissions', { params: { page, pageSize } });
    return data;
  },

  async get(id: number): Promise<SubmissionResponse> {
    const { data } = await api.get<SubmissionResponse>(`/submissions/${id}`);
    return data;
  },

  async retry(id: number): Promise<SubmissionResponse> {
    const { data } = await api.post<SubmissionResponse>(`/submissions/${id}/retry`);
    return data;
  },

  async updateVisibility(id: number, payload: UpdateVisibilityRequest): Promise<SubmissionResponse> {
    const { data } = await api.patch<SubmissionResponse>(`/submissions/${id}/visibility`, payload);
    return data;
  },

  async remove(id: number): Promise<void> {
    await api.delete(`/submissions/${id}`);
  },
};

export default submissionService;
