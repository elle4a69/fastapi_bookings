import { MessageSquareTextIcon, ShieldCheckIcon } from "lucide-react";

export default function SmsAssistantPage() {
  return (
    <section className="flex min-h-0 w-full flex-1 flex-col gap-6 p-4 text-xs md:p-6">
      <div>
        <p className="text-sm font-medium text-primary">Messaging workspace</p>
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight sm:text-3xl">
          <MessageSquareTextIcon className="size-7 text-primary" />
          Messaging
        </h1>
      </div>

      <div
        className="max-w-2xl rounded-lg border bg-card p-5 text-card-foreground shadow-sm"
        role="status"
      >
        <div className="flex items-start gap-3">
          <ShieldCheckIcon className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden="true" />
          <div className="space-y-2">
            <h2 className="text-base font-semibold">
              Staff messaging is managed in Chatwoot
            </h2>
            <p className="text-sm leading-6 text-muted-foreground">
              Use Chatwoot for operator conversations and channel delivery. FastAPI automated and
              local outbound messaging remain disabled until the authenticated Chatwoot integration
              packages are complete.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
