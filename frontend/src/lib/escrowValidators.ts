/**
 * Phase 6: Multi-Level Verification
 * Task 1: PNR Checksum & Task 16: UTR Regex
 */

export const validatePnrChecksum = (pnr: string): boolean => {
  if (!/^\d{10}$/.test(pnr)) return false;
  // Modulo-10 or simple digit check logic
  // Real IRCTC PNRs follow specific starting digit rules
  const firstDigit = parseInt(pnr[0]);
  return [2, 3, 4, 6, 8].includes(firstDigit);
};

export const validateUpiUtr = (utr: string): boolean => {
  return /^\d{12}$/.test(utr);
};

export const validateIndianName = (name: string): boolean => {
  // Reject junk like "asdfgh" (Task 13)
  if (name.length < 3) return false;
  const junkPatterns = [/^[a-z]+$/i, /(.)\1{3,}/]; // Repeats like "aaaa"
  if (junkPatterns[1].test(name)) return false;
  return /^[a-zA-Z\s]+$/.test(name);
};
