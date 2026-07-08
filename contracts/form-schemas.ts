import { z } from "zod";

// --- Provider Validation Schemas ---
export const ProviderCreateSchema = z.object({
  name: z.string().min(1, "Provider name is required"),
  email: z.string().email("Invalid email address").nullable().optional(),
  phone: z.string().nullable().optional(),
  active: z.boolean().default(true),
  is_visible: z.boolean().default(true),
  capacity: z.number().int().min(1, "Capacity must be at least 1").default(1),
  color: z.string().regex(/^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$/, "Invalid hex color").nullable().optional(),
  description: z.string().nullable().optional(),
});

export const ProviderUpdateSchema = ProviderCreateSchema.partial();

// --- Service Validation Schemas ---
export const ServiceCreateSchema = z.object({
  name: z.string().min(1, "Service name is required"),
  description: z.string().nullable().optional(),
  duration: z.number().int().min(1, "Duration must be at least 1 minute"),
  price: z.number().min(0, "Price cannot be negative").nullable().optional(),
  active: z.boolean().default(true),
  is_visible: z.boolean().default(true),
  deposit_amount: z.number().min(0, "Deposit amount cannot be negative").default(0),
  tax_rate_id: z.number().int().nullable().optional(),
  min_group_size: z.number().int().min(1, "Minimum group size must be at least 1").default(1),
  max_group_size: z.number().int().min(1, "Maximum group size must be at least 1").nullable().optional(),
}).refine(
  (data) => !data.max_group_size || data.max_group_size >= data.min_group_size,
  {
    message: "Maximum group size must be greater than or equal to minimum group size",
    path: ["max_group_size"],
  }
);

export const ServiceUpdateSchema = ServiceCreateSchema.partial();

// --- Calendar Note Validation Schemas ---
export const CalendarNoteCreateSchema = z.object({
  provider_id: z.number().int().nullable().optional(),
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Date must be in YYYY-MM-DD format"),
  start_time: z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/, "Start time must be HH:MM format").nullable().optional(),
  end_time: z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/, "End time must be HH:MM format").nullable().optional(),
  text: z.string().min(1, "Calendar note text is required"),
  note_type: z.string().nullable().optional(),
  is_time_blocked: z.boolean().default(false),
});

export const CalendarNoteUpdateSchema = CalendarNoteCreateSchema.partial();
