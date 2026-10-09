import { zodResolver } from "@hookform/resolvers/zod";
import { describe, expect, it } from "vitest";
import { z } from "zod";

// Every form validates through zodResolver, so this pins the pairing of the resolver with the zod
// that is installed. A resolver written for an older zod does not recognise the newer zod's error
// class and rethrows it instead of returning field errors, which leaves an invalid form submit
// with no message on screen (and an uncaught error), while a valid one still works. Nothing else
// exercises that, so a zod or resolvers bump that breaks the pairing would otherwise go unnoticed.

const schema = z.object({
  legal_name: z.string().min(1, "Legal name is required"),
  country_code: z
    .string()
    .length(2, "Must be a 2-letter ISO 3166-1 country code")
    .transform((v) => v.toUpperCase()),
});

const resolver = zodResolver(schema);

// react-hook-form calls a resolver as (values, context, options).
type Options = Parameters<typeof resolver>[2];
const options = { fields: {}, shouldUseNativeValidation: false } as unknown as Options;

describe("zodResolver with the installed zod", () => {
  it("returns field errors with the schema's messages instead of throwing", async () => {
    const result = await resolver({ legal_name: "", country_code: "F" }, undefined, options);

    expect(result.values).toEqual({});
    expect(result.errors).toMatchObject({
      legal_name: { message: "Legal name is required" },
      country_code: { message: "Must be a 2-letter ISO 3166-1 country code" },
    });
  });

  it("returns the parsed values, transforms applied, when the input is valid", async () => {
    const result = await resolver(
      { legal_name: "Acme", country_code: "fr" },
      undefined,
      options,
    );

    expect(result.errors).toEqual({});
    expect(result.values).toEqual({ legal_name: "Acme", country_code: "FR" });
  });
});
