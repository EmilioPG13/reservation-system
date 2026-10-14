import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { components } from './schema'

export type Reservation = components['schemas']['ReservationRead']
export type AdminReservation = components['schemas']['AdminReservationRead']
export type Resource = components['schemas']['ResourceRead']
export type Blackout = components['schemas']['BlackoutRead']

/** The grid refreshes this often so other people's bookings show up without reloading. */
export const POLL_MS = 8000

/** Throws the error body so React Query keeps it on `error`; `data` is never undefined after. */
function unwrap<T>(result: { data?: T; error?: unknown }): T {
  if (result.error !== undefined || result.data === undefined) throw result.error ?? new Error('empty response')
  return result.data
}

export function useAvailability(date: string) {
  return useQuery({
    queryKey: ['availability', date],
    queryFn: async () => unwrap(await api.GET('/availability', { params: { query: { date } } })),
    refetchInterval: POLL_MS,
    placeholderData: keepPreviousData,
  })
}

export function useAdminDay(date: string, enabled: boolean) {
  return useQuery({
    queryKey: ['admin-day', date],
    enabled,
    queryFn: async () => unwrap(await api.GET('/admin/reservations', { params: { query: { date } } })),
    refetchInterval: POLL_MS,
    placeholderData: keepPreviousData,
  })
}

export function useResources() {
  return useQuery({
    queryKey: ['resources'],
    queryFn: async () => unwrap(await api.GET('/resources')),
    staleTime: 60_000,
  })
}

export function useMyReservations() {
  return useQuery({
    queryKey: ['my-reservations'],
    queryFn: async () => unwrap(await api.GET('/reservations', { params: { query: { limit: 100 } } })),
    refetchInterval: POLL_MS * 4,
  })
}

function useRefreshAll() {
  const queryClient = useQueryClient()
  return () => {
    for (const key of ['availability', 'admin-day', 'my-reservations'])
      void queryClient.invalidateQueries({ queryKey: [key] })
  }
}

export function useBook() {
  const refresh = useRefreshAll()
  return useMutation({
    mutationFn: async (input: { resourceId: string; startsAt: string }) =>
      unwrap(await api.POST('/reservations', { body: { resource_id: input.resourceId, starts_at: input.startsAt } })),
    // Success or failure (a 409 means someone else got it), the grid must be fresh.
    onSettled: refresh,
  })
}

export function useCancel(asAdmin: boolean) {
  const refresh = useRefreshAll()
  return useMutation({
    mutationFn: async (reservationId: string) =>
      unwrap(
        asAdmin
          ? await api.POST('/admin/reservations/{reservation_id}/cancel', {
              params: { path: { reservation_id: reservationId } },
            })
          : await api.POST('/reservations/{reservation_id}/cancel', {
              params: { path: { reservation_id: reservationId } },
            }),
      ),
    onSettled: refresh,
  })
}

export function useAdminResources() {
  return useQuery({
    queryKey: ['admin-resources'],
    queryFn: async () => unwrap(await api.GET('/admin/resources')),
  })
}

export function useBlackouts(resourceId: string) {
  return useQuery({
    queryKey: ['blackouts', resourceId],
    queryFn: async () =>
      unwrap(await api.GET('/admin/resources/{resource_id}/blackouts', { params: { path: { resource_id: resourceId } } })),
  })
}

export function useAdminMutations() {
  const queryClient = useQueryClient()
  const done = () => {
    for (const key of ['admin-resources', 'blackouts', 'availability'])
      void queryClient.invalidateQueries({ queryKey: [key] })
  }
  return {
    createCourt: useMutation({
      mutationFn: async (body: components['schemas']['ResourceCreate']) =>
        unwrap(await api.POST('/admin/resources', { body })),
      onSuccess: done,
    }),
    updateCourt: useMutation({
      mutationFn: async (input: { id: string; body: components['schemas']['ResourceUpdate'] }) =>
        unwrap(
          await api.PATCH('/admin/resources/{resource_id}', {
            params: { path: { resource_id: input.id } },
            body: input.body,
          }),
        ),
      onSuccess: done,
    }),
    setHours: useMutation({
      mutationFn: async (input: { id: string; hours: components['schemas']['OpeningHoursItem'][] }) =>
        unwrap(
          await api.PUT('/admin/resources/{resource_id}/opening-hours', {
            params: { path: { resource_id: input.id } },
            body: { hours: input.hours },
          }),
        ),
      onSuccess: done,
    }),
    createBlackout: useMutation({
      mutationFn: async (input: { id: string; body: components['schemas']['BlackoutCreate'] }) =>
        unwrap(
          await api.POST('/admin/resources/{resource_id}/blackouts', {
            params: { path: { resource_id: input.id } },
            body: input.body,
          }),
        ),
      onSuccess: done,
    }),
    deleteBlackout: useMutation({
      mutationFn: async (input: { resourceId: string; blackoutId: string }) => {
        const result = await api.DELETE('/admin/resources/{resource_id}/blackouts/{blackout_id}', {
          params: { path: { resource_id: input.resourceId, blackout_id: input.blackoutId } },
        })
        if (result.error !== undefined) throw result.error
      },
      onSuccess: done,
    }),
  }
}
