import { describe, expect, it } from "vitest";

import { partyFromCompany, pickAddress } from "@/lib/invoiceParties";
import type { AddressType } from "@/types/company";
import type { ContextAddress, ContextCompany } from "@/types/invoice";

function address(id: string, type: AddressType, primary = false): ContextAddress {
  return {
    id,
    address_type: type,
    is_primary: primary,
    line1: `${type} ${id}`,
    line2: null,
    line3: null,
    city: "Paris",
    postal_zone: null,
    country_subdivision: null,
    country_code: "FR",
  };
}

describe("pickAddress", () => {
  it("prefers the registered address for Bill From", () => {
    const picked = pickAddress(
      [address("1", "bill_to"), address("2", "registered", true)],
      "bill_from",
    );
    expect(picked?.id).toBe("2");
  });

  it("prefers the billing address for Bill To", () => {
    const picked = pickAddress(
      [address("1", "registered"), address("2", "bill_to")],
      "bill_to",
    );
    expect(picked?.id).toBe("2");
  });

  it("falls back through ship-to then postal", () => {
    expect(
      pickAddress([address("1", "postal"), address("2", "ship_to")], "bill_from")?.id,
    ).toBe("2");
    expect(pickAddress([address("1", "postal")], "bill_to")?.id).toBe("1");
  });

  it("takes the primary within a type, else the lowest id", () => {
    const two = [address("b", "registered"), address("a", "registered")];
    expect(pickAddress(two, "bill_from")?.id).toBe("a");
    expect(pickAddress([...two, address("c", "registered", true)], "bill_from")?.id).toBe("c");
  });

  it("is null with no address", () => {
    expect(pickAddress([], "bill_to")).toBeNull();
  });
});

describe("partyFromCompany", () => {
  it("uses the display name and the picked address", () => {
    const company: ContextCompany = {
      id: "c",
      display_name: "ACME",
      is_active: true,
      addresses: [address("1", "bill_to")],
    };
    const party = partyFromCompany(company, "bill_to");
    expect(party.name).toBe("ACME");
    expect(party.address.line1).toBe("bill_to 1");
    expect(party.address.line2).toBe("");
  });

  it("is blank with no company or no address", () => {
    expect(partyFromCompany(null, "bill_from").name).toBe("");
    const bare: ContextCompany = {
      id: "c",
      display_name: "X",
      is_active: true,
      addresses: [],
    };
    expect(partyFromCompany(bare, "bill_from").address.line1).toBe("");
  });
});
