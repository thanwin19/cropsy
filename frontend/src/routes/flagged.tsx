import { createFileRoute } from "@tanstack/react-router";
import FlaggedCases from "@/pages/flagged";

export const Route = createFileRoute("/flagged")({
  head: () => ({ meta: [{ title: "Flagged cases — Cropsy" }, { name: "description", content: "Past advisories whose verifier flagged a problem or asked for a retry." }] }),
  component: FlaggedCases,
});
