import { createFileRoute } from "@tanstack/react-router";
import Runs from "@/pages/runs";

export const Route = createFileRoute("/runs")({
  head: () => ({ meta: [{ title: "Execution runs — Cropsy" }, { name: "description", content: "Every stored advisory run with its route trace, cost and latency." }] }),
  component: Runs,
});
