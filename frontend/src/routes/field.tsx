import { createFileRoute } from "@tanstack/react-router";
import { FieldScreen } from "@/features/cropsy/field-screen";
export const Route=createFileRoute("/field")({head:()=>({meta:[{title:"My field — Cropsy"},{name:"description",content:"Daily field report and sample agronomy advisory."},{property:"og:title",content:"My field — Cropsy"},{property:"og:description",content:"Daily field report and sample agronomy advisory."},{property:"og:type",content:"website"},{name:"twitter:card",content:"summary_large_image"}]}),component:FieldScreen});
