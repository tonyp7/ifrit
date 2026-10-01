import { OrganizationLogoCard } from "@/components/configuration/OrganizationLogoCard";

// Each settings card sits in this column, which supplies the padding and the spacing
// between cards (like the other Configuration screens), so cards need no margin of their own.
export function ConfigurationGeneralPage() {
  return (
    <div className="flex flex-col gap-4 p-4">
      <OrganizationLogoCard />
    </div>
  );
}
