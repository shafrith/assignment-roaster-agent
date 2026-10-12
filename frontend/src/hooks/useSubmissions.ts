import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  DEFAULT_PAGE_SIZE,
  submissionKeys,
  submissionService,
  type CreateSubmissionRequest,
} from '../services/submissionService';
import { isTerminalStatus } from '../lib/format';
import type { SubmissionResponse } from '../types/api';

/** Dashboard refresh cadence while any visible row is still pending/analyzing/roasting. */
export const LIST_POLL_INTERVAL_MS = 5000;

/** Paginated list of the current user's submissions; auto-refreshes while rows are in progress (COR-8). */
export function useSubmissions(page: number, pageSize: number = DEFAULT_PAGE_SIZE) {
  return useQuery({
    queryKey: submissionKeys.list(page, pageSize),
    queryFn: () => submissionService.list(page, pageSize),
    placeholderData: keepPreviousData,
    refetchInterval: (query) => {
      if (query.state.status === 'error') return false;
      const items = query.state.data?.items ?? [];
      return items.some((item) => !isTerminalStatus(item.status)) ? LIST_POLL_INTERVAL_MS : false;
    },
  });
}

/** POST /submissions → navigates to /roasts/:id on success. */
export function useCreateSubmission() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: (payload: CreateSubmissionRequest) => submissionService.create(payload),
    onSuccess: (submission: SubmissionResponse) => {
      queryClient.setQueryData(submissionKeys.detail(submission.id), submission);
      void queryClient.invalidateQueries({ queryKey: submissionKeys.lists() });
      navigate(`/roasts/${submission.id}`);
    },
  });
}

/** POST /submissions/:id/retry (only valid when failed). Polling resumes via useSubmission. */
export function useRetry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => submissionService.retry(id),
    onSuccess: (submission: SubmissionResponse) => {
      queryClient.setQueryData(submissionKeys.detail(submission.id), submission);
      void queryClient.invalidateQueries({ queryKey: submissionKeys.lists() });
    },
  });
}

export interface ToggleVisibilityVariables {
  id: number;
  isPublic: boolean;
}

export function useToggleVisibility() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, isPublic }: ToggleVisibilityVariables) =>
      submissionService.updateVisibility(id, { isPublic }),
    onSuccess: (submission: SubmissionResponse) => {
      queryClient.setQueryData(submissionKeys.detail(submission.id), submission);
      void queryClient.invalidateQueries({ queryKey: submissionKeys.lists() });
    },
  });
}

export function useDeleteSubmission() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => submissionService.remove(id),
    onSuccess: (_data: void, id: number) => {
      queryClient.removeQueries({ queryKey: submissionKeys.detail(id) });
      void queryClient.invalidateQueries({ queryKey: submissionKeys.lists() });
    },
  });
}
