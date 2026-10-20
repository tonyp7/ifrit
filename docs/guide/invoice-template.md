# The invoice template

The PDF of an invoice is made from a template: an ordinary **OpenDocument Text** (`.odt`) file that
you edit in LibreOffice Writer. It holds the layout (your logo, your colours, your fixed texts)
and **placeholders** such as `{{invoice_number}}` that are replaced by the invoice's values. One
placeholder, `{{invoice_lines}}`, stands for the whole table of lines, subtotal, taxes and total.

An administrator manages the template under **Configuration > Invoices > Invoice Template**. Out
of the box the **default template** that ships with the application is used.

## Changing the template

1. Choose **Download** on the Invoice Template card. You get the template in use, so you always
   start from what you have now.
2. Open it in LibreOffice Writer and edit it: change the logo, the wording, the fonts and colours,
   move things around.
3. Choose **Upload…** and pick your file. Nothing changes yet: the application checks it, makes a
   sample PDF with made-up values and shows it to you, with any warnings.
4. If you like it, choose **Use this template**. If not, **Cancel**, edit the file and try again.

From then on, previews and newly issued invoices use your template. Invoices that were already
issued keep the PDF they were issued with: they are never made again.

**Reset to default** discards your template and brings back the default one. It asks first, and is
disabled while the default is already in use. There is no separate remove button.

## Placeholders

Type a placeholder as plain text in the document: two braces, a lowercase name, two braces, as in
`{{invoice_number}}`. It can be in the body, in a table, in a text box and in a page header or
footer. Give it the formatting you want (bold, a colour, a size): the value takes the formatting of
the first character of the placeholder.

- **Optional rows.** Add a question mark, as in `{{payee_bank_name?}}`, and the whole paragraph
  that holds it disappears when the value is empty. Use it for lines such as `Bank: {{payee_bank_name?}}`
  so a missing bank name leaves no empty label.
- **Several lines.** Some placeholders stand for a list and become one paragraph per item, in the
  style of the paragraph they are in: `{{references}}`, `{{bill_to_address_lines}}`,
  `{{bill_from_address_lines}}`, `{{bill_to_identifiers}}`, `{{bill_from_identifiers}}` and
  `{{payee_bank_address_lines}}`. Each must be **alone in its paragraph**.
- **The lines table.** `{{invoice_lines}}` must appear **exactly once**, alone in a paragraph in
  the body of the document (not in a header or footer). It becomes a table with the columns
  Description, Quantity, Unit, Unit Price, Currency and Total Price, then the subtotal, one row per
  tax and the total. The header row repeats on every page and a row is never split across two
  pages.
- **Values are English.** Unit names, payment terms, month and country names and the like are
  written in English whatever the template says. The fixed text around them is yours, in any
  language your fonts support.
- **Not placeholders.** The logo is simply a picture in the template (embedded, not linked). Page
  numbers are Writer's own page number and page count fields.

### The look of the lines table

The table's structure and column widths are fixed, but you control its text through six paragraph
styles. Define them in the template (Writer's Styles panel) and the table uses them; leave one out
and a plain built-in look is used.

| Style name | Used for |
| --- | --- |
| `InvoiceLinesHeader` | Header cells with text (Description, Unit, Currency) |
| `InvoiceLinesHeaderNumber` | Header cells over a number column |
| `InvoiceLinesCell` | Text cells of the lines |
| `InvoiceLinesNumber` | Number cells of the lines |
| `InvoiceLinesLabel` | The Subtotal and tax labels |
| `InvoiceLinesTotal` | The Total row |

### The DRAFT mark

The default template carries a large gray **DRAFT** behind the text of every page. It is a shape
in the page header holding the placeholder `{{draft_watermark}}`, which prints `DRAFT` on a draft
and nothing on an issued invoice. Restyle it like any shape, or delete the shape if you do not want
it; the upload then warns you that previews will show no mark. A voided invoice gets its **VOIDED**
mark from the application, not from the template.

### Fonts

The application ships the Liberation fonts (Sans, Serif, Mono). A template that uses another font
is accepted, with a warning, and the PDF uses a substitute. Text in a script the fonts do not cover
(Chinese, Japanese, Arabic, Thai and others) will not print correctly.

## What is refused

The upload is checked before it is used, and every problem found is listed with where it is. A
template is refused when it:

- is not an OpenDocument Text file, is larger than 5 MB or is not a sound archive;
- contains macros, scripts, embedded objects or plug-ins;
- links to anything outside the document, including linked pictures and web links (embed pictures,
  and keep links to places inside the document only);
- uses a placeholder that does not exist, writes one with capitals or spaces, or puts a list
  placeholder in a paragraph with other text;
- does not have `{{invoice_lines}}` exactly once in the body; or
- cannot be turned into a PDF, or its sample invoice, one line and one tax, takes more than one
  page.

If the PDF engine is not available, a template cannot be checked and the upload is refused with a
message; try again later.

## Placeholder reference

The same list is on the Invoice Template card, under **Placeholders**.

### Document

| Placeholder | What it prints | Kind | Example |
| --- | --- | --- | --- |
| `{{document_name}}` | The document name setting (Invoice by default) | text | Invoice |
| `{{invoice_number}}` | The invoice number | text | INV-2026-0043 |
| `{{invoice_date}}` | The invoice date | text | 3 September 2026 |
| `{{due_date}}` | The due date | text | 3 October 2026 |
| `{{payment_terms}}` | The payment terms | text | NET 30 |
| `{{payment_terms_code}}` | The payment terms as a code | text | net_30 |
| `{{period_start}}` | Start of the billed period | text | 1 August 2026 |
| `{{period_end}}` | End of the billed period | text | 31 August 2026 |
| `{{period}}` | The billed period | text | 1-31 August 2026 |
| `{{status}}` | Draft or Issued | text | Issued |
| `{{issued_at}}` | When the invoice was issued | text | 3 September 2026 14:05 |
| `{{generated_at}}` | When this PDF was made | text | 3 September 2026 14:05 |
| `{{currency_code}}` | The invoice currency | text | USD |
| `{{line_count}}` | The number of lines | text | 3 |
| `{{draft_watermark}}` | DRAFT on a draft, empty otherwise | text | DRAFT |

### Parties

Every row exists twice: `bill_from_` is the vendor (the company issuing the invoice) and `bill_to_` is the client. The table shows the `bill_from_` names; `{{bill_to_name}}`, `{{bill_to_address_lines}}` and so on work the same way.

| Placeholder | What it prints | Kind | Example |
| --- | --- | --- | --- |
| `{{bill_from_name}}` | The vendor's name | text | Acme Pte Ltd |
| `{{bill_from_line1}}` | First address line of the vendor | text | 8 Ah Soo Garden |
| `{{bill_from_line2}}` | Second address line of the vendor | text | Unit 4 |
| `{{bill_from_line3}}` | Third address line of the vendor | text | - |
| `{{bill_from_city}}` | City of the vendor | text | Singapore |
| `{{bill_from_postal_zone}}` | Postal code of the vendor | text | 539960 |
| `{{bill_from_country_subdivision}}` | State or province of the vendor | text | - |
| `{{bill_from_country_code}}` | ISO country code of the vendor | text | SG |
| `{{bill_from_country}}` | Country of the vendor, in English | text | Singapore |
| `{{bill_from_address}}` | The vendor's whole address on one line | text | 8 Ah Soo Garden, 539960 Singapore, Singapore |
| `{{bill_from_address_lines}}` | The vendor's address, one paragraph per line | one paragraph per item | 8 Ah Soo Garden / 539960 Singapore / Singapore |
| `{{bill_from_vat_id}}` | The vendor's primary VAT identifier | text | SG123456789 |
| `{{bill_from_registration_id}}` | The vendor's primary legal registration identifier | text | 201912345K |
| `{{bill_from_peppol_id}}` | The vendor's primary Peppol participant identifier | text | 0195:SGUENT08GA0028A |
| `{{bill_from_identifiers}}` | The vendor's identifiers, one paragraph each | one paragraph per item | VAT: SG123456789 |

### Payment

| Placeholder | What it prints | Kind | Example |
| --- | --- | --- | --- |
| `{{payment_means}}` | How to pay | text | Bank transfer |
| `{{payment_means_code}}` | How to pay, as a code | text | 42 |
| `{{payee_account_name}}` | The account holder | text | Acme Pte Ltd |
| `{{payee_account_scheme}}` | IBAN or Other | text | IBAN |
| `{{payee_account_identifier}}` | The account number (IBAN in groups of four) | text | SG12 3456 7890 1234 |
| `{{payee_account_identifier_raw}}` | The account number as stored | text | SG1234567890123456 |
| `{{payee_currency_code}}` | The account's currency | text | USD |
| `{{payee_bic}}` | The bank's BIC (SWIFT) | text | DBSSSGSG |
| `{{payee_bank_name}}` | The bank's name | text | DBS Bank |
| `{{payee_bank_line1}}` | First address line of the bank | text | 12 Marina Boulevard |
| `{{payee_bank_line2}}` | Second address line of the bank | text | - |
| `{{payee_bank_line3}}` | Third address line of the bank | text | - |
| `{{payee_bank_city}}` | City of the bank | text | Singapore |
| `{{payee_bank_postal_zone}}` | Postal code of the bank | text | 018982 |
| `{{payee_bank_country_subdivision}}` | State or province of the bank | text | - |
| `{{payee_bank_country_code}}` | ISO country code of the bank | text | SG |
| `{{payee_bank_country}}` | Country of the bank, in English | text | Singapore |
| `{{payee_bank_address}}` | The bank's address on one line | text | 12 Marina Boulevard, 018982 Singapore, Singapore |
| `{{payee_bank_address_lines}}` | The bank's address, one paragraph per line | one paragraph per item | 12 Marina Boulevard / 018982 Singapore |

### Amounts

| Placeholder | What it prints | Kind | Example |
| --- | --- | --- | --- |
| `{{subtotal}}` | The subtotal | text | 6,000.00 |
| `{{tax_total}}` | The sum of the taxes | text | 420.00 |
| `{{total}}` | The total | text | 6,420.00 |
| `{{subtotal_with_currency}}` | The subtotal with the currency | text | USD 6,000.00 |
| `{{tax_total_with_currency}}` | The taxes with the currency | text | USD 420.00 |
| `{{total_with_currency}}` | The total with the currency | text | USD 6,420.00 |

### References

| Placeholder | What it prints | Kind | Example |
| --- | --- | --- | --- |
| `{{references}}` | The references, one paragraph each | one paragraph per item | Purchase order: 1070000772 |
| `{{reference_purchase_order}}` | The values of the purchase order references | text | PO-1, PO-2 |
| `{{reference_sales_order}}` | The values of the sales order references | text | PO-1, PO-2 |
| `{{reference_contract}}` | The values of the contract references | text | PO-1, PO-2 |
| `{{reference_buyer_reference}}` | The values of the buyer reference references | text | PO-1, PO-2 |
| `{{reference_accounting_reference}}` | The values of the accounting reference references | text | PO-1, PO-2 |
| `{{reference_project_reference}}` | The values of the project reference references | text | PO-1, PO-2 |
| `{{reference_document_reference}}` | The values of the document reference references | text | PO-1, PO-2 |
| `{{reference_custom}}` | The custom references as Label: value | text | Cost centre: 4410 |

### The lines table

| Placeholder | What it prints |
| --- | --- |
| `{{invoice_lines}}` | The line-items table: header, one row per line, subtotal, taxes and total. Alone in its paragraph, exactly once. |
