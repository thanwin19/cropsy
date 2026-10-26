import { createFileRoute } from "@tanstack/react-router";
import Settings from "@/pages/settings";

export const Route = createFileRoute("/settings")({
  head: () => ({ meta: [{ title: "Settings — Cropsy" }, { name: "description", content: "Backend connection and demo mode." }] }),
  component: Settings,
});
