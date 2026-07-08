import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { components } from "./types";

type Provider = components["schemas"]["Provider"];
type ProviderCreate = components["schemas"]["ProviderCreate"];
type ProviderUpdate = components["schemas"]["ProviderUpdate"];

type Service = components["schemas"]["Service"];
type ServiceCreate = components["schemas"]["ServiceCreate"];
type ServiceUpdate = components["schemas"]["ServiceUpdate"];

type CalendarNoteOut = components["schemas"]["CalendarNoteOut"];
type CalendarNoteCreate = components["schemas"]["CalendarNoteCreate"];
type CalendarNoteUpdate = components["schemas"]["CalendarNoteUpdate"];

const API_BASE = "/api/admin";

// --- Provider Hooks ---
export function useListProviders() {
  return useQuery({
    queryKey: ["providers"],
    queryFn: async () => {
      const { data } = await axios.get(`${API_BASE}/providers`);
      return data.data as Provider[];
    },
  });
}

export function useCreateProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (newProvider: ProviderCreate) => {
      const { data } = await axios.post(`${API_BASE}/providers`, newProvider);
      return data.data as Provider;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["providers"] });
    },
  });
}

export function useUpdateProvider(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (updatedProvider: ProviderUpdate) => {
      const { data } = await axios.put(`${API_BASE}/providers/${id}`, updatedProvider);
      return data.data as Provider;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["providers"] });
      queryClient.invalidateQueries({ queryKey: ["providers", id] });
    },
  });
}

// --- Service Hooks ---
export function useListServices() {
  return useQuery({
    queryKey: ["services"],
    queryFn: async () => {
      const { data } = await axios.get(`${API_BASE}/services`);
      return data.data as Service[];
    },
  });
}

export function useCreateService() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (newService: ServiceCreate) => {
      const { data } = await axios.post(`${API_BASE}/services`, newService);
      return data.data as Service;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["services"] });
    },
  });
}

export function useUpdateService(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (updatedService: ServiceUpdate) => {
      const { data } = await axios.put(`${API_BASE}/services/${id}`, updatedService);
      return data.data as Service;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["services"] });
      queryClient.invalidateQueries({ queryKey: ["services", id] });
    },
  });
}

// --- Calendar Note Hooks ---
export function useListCalendarNotes(params?: { provider_id?: number; date_from?: string; date_to?: string }) {
  return useQuery({
    queryKey: ["calendar-notes", params],
    queryFn: async () => {
      const { data } = await axios.get(`${API_BASE}/calendar-notes`, { params });
      return data.data as CalendarNoteOut[];
    },
  });
}

export function useCreateCalendarNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (newNote: CalendarNoteCreate) => {
      const { data } = await axios.post(`${API_BASE}/calendar-notes`, newNote);
      return data.data as CalendarNoteOut;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calendar-notes"] });
    },
  });
}

export function useUpdateCalendarNote(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (updatedNote: CalendarNoteUpdate) => {
      const { data } = await axios.put(`${API_BASE}/calendar-notes/${id}`, updatedNote);
      return data.data as CalendarNoteOut;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calendar-notes"] });
    },
  });
}
