const CROP_WORDS = ["rice", "paddy", "maize", "corn", "sugarcane", "coconut", "banana", "groundnut", "cotton", "blackgram", "chilli", "turmeric", "tomato", "sorghum", "cumbu", "bajra", "ragi", "wheat", "redgram", "greengram", "cowpea", "horsegram", "bengalgram", "gram", "soybean", "sesame", "castor", "sunflower", "mango", "brinjal", "onion", "okra", "potato"];

/** True when the question is general knowledge ("how does photosynthesis work") or about a crop other than the selected parcel's; such a question must not be answered from the parcel's record. */
export function isGeneralQuestion(text: string, parcelCrop: string | null): boolean {
  const t = text.toLowerCase();
  const fieldWords = /\b(my|this|here|field|parcel|farm|plot|today|tomorrow|week|now|current|currently|tm-?\d+)\b/.test(t);
  const named = CROP_WORDS.filter((c) => new RegExp(`\\b${c}\\b`).test(t));
  const pc = (parcelCrop || "").toLowerCase();
  if (named.length && pc && !named.some((c) => pc.includes(c) || c.includes(pc))) return !fieldWords || named.length > 0;
  if (!fieldWords && /^(what (is|are|does)|how (does|do)|why|explain|define|difference|compare|which (is|are))\b/.test(t) && !named.some((c) => pc.includes(c))) return true;
  return false;
}

