import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { AskScreen } from "@/features/cropsy/ask-screen";
const searchSchema=z.object({parcel:z.string().regex(/^TM-\d{2,3}$/).optional().catch(undefined)});
export const Route=createFileRoute("/")({validateSearch:searchSchema,head:()=>({meta:[{title:"Ask Cropsy — Then Malai"},{name:"description",content:"Parcel-aware agricultural advice for Then Malai."},{property:"og:title",content:"Ask Cropsy — Then Malai"},{property:"og:description",content:"Parcel-aware agricultural advice for Then Malai."},{property:"og:type",content:"website"},{name:"twitter:card",content:"summary_large_image"}]}),component:Index});
function Index(){const {parcel}=Route.useSearch();return <AskScreen initialParcel={parcel}/>}
