import { describe, it, expect } from "vitest";
import { MIDNIGHT } from "@/lib/theme";
it("exposes the midnight palette", () => {
  expect(MIDNIGHT.emerald).toBe("#34d399");
  expect(MIDNIGHT.bg).toBe("#0b0f17");
  expect(MIDNIGHT.axis).toBeTruthy();
});
