import { Component, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export function PageLoadErrorView({ onReload }: { onReload: () => void }) {
  const { t } = useTranslation(["common"]);

  return (
    <div className="p-4">
      <Alert variant="destructive">
        <AlertTitle>{t("This page couldn't be loaded")}</AlertTitle>
        <AlertDescription className="flex flex-col items-start gap-2">
          {t("The app may have been updated. Reload to get the latest version.")}
          <Button type="button" size="sm" variant="outline" onClick={onReload}>
            {t("Reload")}
          </Button>
        </AlertDescription>
      </Alert>
    </div>
  );
}

interface PageLoadErrorBoundaryProps {
  children: ReactNode;
  /** Clearing the error when this changes (the route) lets the user move on to another
   * page from the navigation that stays on screen, instead of being stuck on the message. */
  resetKey?: string;
}

interface PageLoadErrorBoundaryState {
  hasError: boolean;
}

// A page's code is downloaded the first time it is visited, and that can fail: a tab left
// open across a redeploy still asks for the old hashed file, which no longer exists (the web
// server answers an unknown path with index.html, which a browser cannot run as a script).
// Without a boundary the whole app would unmount into a blank page. A class component
// because that is the only way React offers to catch an error thrown while rendering.
export class PageLoadErrorBoundary extends Component<
  PageLoadErrorBoundaryProps,
  PageLoadErrorBoundaryState
> {
  state: PageLoadErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): PageLoadErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    console.error("A page failed to load:", error);
  }

  componentDidUpdate(previous: PageLoadErrorBoundaryProps) {
    if (this.state.hasError && previous.resetKey !== this.props.resetKey) {
      this.setState({ hasError: false });
    }
  }

  render() {
    if (this.state.hasError) {
      return <PageLoadErrorView onReload={() => window.location.reload()} />;
    }
    return this.props.children;
  }
}
