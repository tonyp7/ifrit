import { Spinner } from "@/components/ui/spinner";

// Shown while a lazily loaded page's code is downloaded. Tall enough that the layout around
// it does not collapse and then jump when the page arrives.
export function PageLoading() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner className="text-muted-foreground size-6" />
    </div>
  );
}
