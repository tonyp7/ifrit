import { DocumentNameCard } from "@/components/configuration/DocumentNameCard";
import { InvoiceNumberingCard } from "@/components/configuration/InvoiceNumberingCard";

// Laid out like the General tab: the column supplies the padding and the spacing between
// cards, so cards need no margin of their own.
export function ConfigurationInvoicesPage() {
  return (
    <div className="flex flex-col gap-4 p-4">
      <DocumentNameCard />
      <InvoiceNumberingCard />
    </div>
  );
}
