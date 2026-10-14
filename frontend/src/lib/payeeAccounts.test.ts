import { describe, expect, it } from "vitest";

import {
  BLANK_ADDRESS_FIELDS,
  BLANK_PAYEE_ACCOUNT_VALUES,
  compactIban,
  formatAccountIdentifier,
  isValidBic,
  isValidIban,
  missingBankAddressFields,
  schemeForPaymentMeans,
  toPayeeAccountFormValues,
  toPayeeAccountInput,
} from "@/lib/payeeAccounts";
import type { PayeeAccount } from "@/types/company";

describe("isValidIban", () => {
  it("accepts a well-formed IBAN with a valid checksum", () => {
    expect(isValidIban("BE71096123456769")).toBe(true);
    expect(isValidIban("NL91ABNA0417164300")).toBe(true);
  });

  it("rejects a wrong checksum, a bad shape and a non-compact value", () => {
    expect(isValidIban("BE71096123456768")).toBe(false);
    expect(isValidIban("1E71096123456769")).toBe(false);
    expect(isValidIban("BE71 0961 2345 6769")).toBe(false);
  });

  it("is used on the compact form", () => {
    expect(isValidIban(compactIban(" be71 0961 2345 6769 "))).toBe(true);
  });
});

describe("isValidBic", () => {
  it("accepts 8 or 11 letters or digits, in any case", () => {
    expect(isValidBic("GEBABEBB")).toBe(true);
    expect(isValidBic("gebabebb36a")).toBe(true);
  });

  it("rejects any other length", () => {
    expect(isValidBic("GEBABEBB0")).toBe(false);
    expect(isValidBic("GEBA")).toBe(false);
  });
});

describe("formatAccountIdentifier", () => {
  it("groups an IBAN in fours", () => {
    expect(formatAccountIdentifier("iban", "BE71096123456769")).toBe("BE71 0961 2345 6769");
    expect(formatAccountIdentifier("iban", "NL91ABNA0417164300")).toBe(
      "NL91 ABNA 0417 1643 00",
    );
  });

  it("leaves other schemes as stored", () => {
    expect(formatAccountIdentifier("other", "123-456789-0")).toBe("123-456789-0");
  });
});

describe("missingBankAddressFields", () => {
  it("asks for nothing when the address is empty", () => {
    expect(missingBankAddressFields(BLANK_ADDRESS_FIELDS)).toEqual([]);
  });

  it("asks for line 1, city and country once any field is filled", () => {
    expect(missingBankAddressFields({ ...BLANK_ADDRESS_FIELDS, city: "Brussels" })).toEqual([
      "line1",
      "country_code",
    ]);
  });
});

describe("toPayeeAccountInput", () => {
  const values = {
    ...BLANK_PAYEE_ACCOUNT_VALUES,
    account_identifier: "be71 0961 2345 6769",
    currency_code: "EUR",
    bic: " gebabebb ",
  };

  it("sends no bank address when every address field is empty", () => {
    const input = toPayeeAccountInput({
      ...values,
      bank_address: { ...BLANK_ADDRESS_FIELDS, line2: "  " },
    });
    expect(input.bank_address).toBeNull();
    expect(input.account_identifier).toBe("BE71096123456769");
    expect(input.bic).toBe("GEBABEBB");
    expect(input.account_name).toBeNull();
  });

  it("sends a filled address with blank optional lines as null", () => {
    const input = toPayeeAccountInput({
      ...values,
      bank_address: {
        ...BLANK_ADDRESS_FIELDS,
        line1: "Montagne du Parc 3",
        city: "Brussels",
        country_code: "be",
      },
    });
    expect(input.bank_address).toEqual({
      line1: "Montagne du Parc 3",
      line2: null,
      line3: null,
      city: "Brussels",
      postal_zone: null,
      country_subdivision: null,
      country_code: "BE",
    });
  });

  it("keeps a national account number as typed, only trimmed", () => {
    const input = toPayeeAccountInput({
      ...values,
      payment_means_code: "30",
      account_scheme: "other",
      account_identifier: " 123-456789-0 ",
    });
    expect(input.account_identifier).toBe("123-456789-0");
  });
});

describe("toPayeeAccountFormValues", () => {
  it("round-trips an account for Edit and Duplicate", () => {
    const account: PayeeAccount = {
      id: "a",
      company_id: "c",
      payment_means_code: "58",
      account_scheme: "iban",
      account_identifier: "BE71096123456769",
      account_name: null,
      currency_code: "EUR",
      bic: "GEBABEBB",
      bank_name: null,
      bank_address: null,
      is_primary: true,
    };
    const values = toPayeeAccountFormValues(account);
    expect(values.account_identifier).toBe("BE71 0961 2345 6769");
    expect(values.bank_address).toEqual(BLANK_ADDRESS_FIELDS);
    const input = toPayeeAccountInput(values);
    expect(input).toMatchObject({
      account_identifier: "BE71096123456769",
      bic: "GEBABEBB",
      bank_address: null,
      is_primary: true,
    });
  });
});

describe("schemeForPaymentMeans", () => {
  it("forces IBAN for a SEPA credit transfer", () => {
    expect(schemeForPaymentMeans("58", "other")).toBe("iban");
  });

  it("keeps the current scheme for any other code", () => {
    expect(schemeForPaymentMeans("30", "other")).toBe("other");
    expect(schemeForPaymentMeans("42", "iban")).toBe("iban");
  });
});
