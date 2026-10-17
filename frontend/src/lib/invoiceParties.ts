import { BLANK_ADDRESS_FIELDS, type AddressFieldValues } from "@/lib/payeeAccounts";
import type { AddressType, BankAddress } from "@/types/company";
import type { ContextAddress, ContextCompany } from "@/types/invoice";

export type PartySide = "bill_from" | "bill_to";

// Which of a company's addresses to pre-fill, by type, first present wins: the vendor
// bills from where it is registered, the client is billed where it asks to be billed.
const TYPE_ORDER: Record<PartySide, AddressType[]> = {
  bill_from: ["registered", "bill_to", "ship_to", "postal"],
  bill_to: ["bill_to", "registered", "ship_to", "postal"],
};

/** The address to pre-fill for a party: the first type present in the side's order, and
 * within it the primary address, else the one with the lowest id. Null with no address. */
export function pickAddress(
  addresses: ContextAddress[],
  side: PartySide,
): ContextAddress | null {
  for (const type of TYPE_ORDER[side]) {
    const candidates = addresses
      .filter((address) => address.address_type === type)
      .sort((a, b) => Number(b.is_primary) - Number(a.is_primary) || a.id.localeCompare(b.id));
    if (candidates.length) return candidates[0];
  }
  return null;
}

/** An address as the form's plain string fields. */
export function addressToFields(address: BankAddress | null): AddressFieldValues {
  if (!address) return BLANK_ADDRESS_FIELDS;
  return {
    line1: address.line1,
    line2: address.line2 ?? "",
    line3: address.line3 ?? "",
    city: address.city,
    postal_zone: address.postal_zone ?? "",
    country_subdivision: address.country_subdivision ?? "",
    country_code: address.country_code,
  };
}

export interface PartyFormValues {
  name: string;
  address: AddressFieldValues;
}

/** A party pre-filled from a company: its display name (trading name, else legal name) and
 * the address `pickAddress` chooses. Everything stays editable afterwards. */
export function partyFromCompany(
  company: ContextCompany | null,
  side: PartySide,
): PartyFormValues {
  if (!company) return { name: "", address: BLANK_ADDRESS_FIELDS };
  return {
    name: company.display_name,
    address: addressToFields(pickAddress(company.addresses, side)),
  };
}
