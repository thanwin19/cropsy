import { createFileRoute } from "@tanstack/react-router";
import { TrustScreen } from "@/features/cropsy/trust-screen";
export const Route=createFileRoute("/trust")({head:()=>({meta:[{title:"Evidence & trace — Cropsy"},{name:"description",content:"Inspect sources, checks, limitations and the advisory route trace."},{property:"og:title",content:"Evidence & trace — Cropsy"},{property:"og:description",content:"Inspect sources, checks, limitations and the advisory route trace."},{property:"og:type",content:"website"},{name:"twitter:card",content:"summary_large_image"}]}),component:TrustScreen});
