import { useTranslation } from "react-i18next";
import type { UseFormReturn } from "react-hook-form";

import type { InvoiceFormValues } from "@/components/invoices/invoiceForm";
import { IssuedDates } from "@/components/invoices/IssuedInvoiceDetails";
import { PayeeAccountFields } from "@/components/invoices/PayeeAccountFields";
import { PaymentTermsField } from "@/components/invoices/PaymentTermsField";
import type { ContextPayeeAccount, InvoiceDetail, PaymentTerms } from "@/types/invoice";

interface PaymentSectionProps {
  form: UseFormReturn<InvoiceFormValues>;
  accounts: ContextPayeeAccount[];
  invoiceCurrency: string | null;
  paymentTerms: PaymentTerms | null;
  dueDate: string | null;
  today: Date;
  onTermsChange: (value: {
    paymentTerms: PaymentTerms | null;
    dueDate: string | null;
  }) => void;
  /** An issued or void invoice: the dates it was issued with, and nothing to edit. */
  readOnly: boolean;
  detail: InvoiceDetail | null;
}

/** How the invoice asks to be paid: the payment terms, then the payee account, each its own
 * bordered group across the full width. */
export function PaymentSection({
  form,
  accounts,
  invoiceCurrency,
  paymentTerms,
  dueDate,
  today,
  onTermsChange,
  readOnly,
  detail,
}: PaymentSectionProps) {
  const { t } = useTranslation(["invoices"]);
  return (
    <div className="flex flex-col gap-4">
      {readOnly && detail ? (
        <fieldset className="flex flex-col gap-2 rounded-md border p-4">
          <legend className="px-1 text-sm font-medium">{t("Payment terms")}</legend>
          <IssuedDates detail={detail} />
        </fieldset>
      ) : (
        <PaymentTermsField
          paymentTerms={paymentTerms}
          dueDate={dueDate}
          today={today}
          disabled={readOnly}
          onChange={onTermsChange}
        />
      )}
      <PayeeAccountFields
        accounts={accounts}
        invoiceCurrency={invoiceCurrency}
        form={form}
        disabled={readOnly}
      />
    </div>
  );
}
