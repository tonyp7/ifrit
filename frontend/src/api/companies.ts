import { apiClient } from "@/api/client";
import type {
  Address,
  AddressInput,
  CompanyDetail,
  CompanyInput,
  CompanyListResponse,
  PartyIdentifier,
  PartyIdentifierInput,
} from "@/types/company";

export function listCompanies(params: {
  search?: string;
  page?: number;
  is_vendor?: boolean;
  is_active?: boolean;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
}) {
  const query = new URLSearchParams();
  if (params.search) query.set("search", params.search);
  query.set("page", String(params.page ?? 1));
  if (params.is_vendor !== undefined) query.set("is_vendor", String(params.is_vendor));
  if (params.is_active !== undefined) query.set("is_active", String(params.is_active));
  if (params.sort_by) query.set("sort_by", params.sort_by);
  if (params.sort_dir) query.set("sort_dir", params.sort_dir);
  return apiClient.get<CompanyListResponse>(`/companies?${query.toString()}`);
}

export function getCompany(companyId: string) {
  return apiClient.get<CompanyDetail>(`/companies/${companyId}`);
}

export function createCompany(payload: CompanyInput) {
  return apiClient.post<CompanyDetail>("/companies", payload);
}

export function updateCompany(companyId: string, payload: CompanyInput) {
  return apiClient.patch<CompanyDetail>(`/companies/${companyId}`, payload);
}

export function duplicateCompany(companyId: string) {
  return apiClient.post<CompanyDetail>(`/companies/${companyId}/duplicate`);
}

export function deactivateCompany(companyId: string) {
  return apiClient.post<void>(`/companies/${companyId}/deactivate`);
}

export function addIdentifier(companyId: string, payload: PartyIdentifierInput) {
  return apiClient.post<PartyIdentifier>(`/companies/${companyId}/identifiers`, payload);
}

export function updateIdentifier(
  companyId: string,
  identifierId: string,
  payload: PartyIdentifierInput,
) {
  return apiClient.patch<PartyIdentifier>(
    `/companies/${companyId}/identifiers/${identifierId}`,
    payload,
  );
}

export function deleteIdentifier(companyId: string, identifierId: string) {
  return apiClient.delete<void>(`/companies/${companyId}/identifiers/${identifierId}`);
}

export function addAddress(companyId: string, payload: AddressInput) {
  return apiClient.post<Address>(`/companies/${companyId}/addresses`, payload);
}

export function updateAddress(companyId: string, addressId: string, payload: AddressInput) {
  return apiClient.patch<Address>(`/companies/${companyId}/addresses/${addressId}`, payload);
}

export function deleteAddress(companyId: string, addressId: string) {
  return apiClient.delete<void>(`/companies/${companyId}/addresses/${addressId}`);
}
