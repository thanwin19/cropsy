import { describe, expect, it } from "vitest";
import { isGeneralQuestion } from "./generalQuestion";

describe("a selected parcel must not swallow general questions", () => {
  it("general knowledge and other-crop questions are general", () => {
    expect(isGeneralQuestion("how does photosynthesis work", "Rice")).toBe(true);
    expect(isGeneralQuestion("what does soil pH 8.4 mean", "Rice")).toBe(true);
    expect(isGeneralQuestion("what is the seed rate for cowpea", "Rice")).toBe(true);
    expect(isGeneralQuestion("turmeric basal FYM dose per hectare", "Rice")).toBe(true);
  });
  it("questions about the parcel stay on the parcel", () => {
    expect(isGeneralQuestion("will it rain at my field this week", "Rice")).toBe(false);
    expect(isGeneralQuestion("when should I apply urea now", "Rice")).toBe(false);
    expect(isGeneralQuestion("how to control blast in rice", "Rice")).toBe(false);
    expect(isGeneralQuestion("irrigation advice", "Rice")).toBe(false);
  });
});
