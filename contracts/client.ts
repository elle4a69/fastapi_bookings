import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./types.js";

export interface BookingApiClientOptions {
  baseUrl: string;
  tenant: string;
  token: string | (() => string | Promise<string>);
  fetch?: typeof globalThis.fetch;
}

/** Create a fully typed client for either admin or widget operations. */
export function createBookingApiClient(options: BookingApiClientOptions) {
  const auth: Middleware = {
    async onRequest({ request }) {
      const token = typeof options.token === "function" ? await options.token() : options.token;
      request.headers.set("X-Tenant", options.tenant);
      request.headers.set("X-Token", token);
      return request;
    },
  };
  const client = createClient<paths>({ baseUrl: options.baseUrl, fetch: options.fetch });
  client.use(auth);
  return client;
}

export type BookingApiClient = ReturnType<typeof createBookingApiClient>;
