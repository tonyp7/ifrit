// Event bridge between api/client.ts (a plain module with no React context access)
// and AuthProvider.tsx (the sole owner of `user` state and the only thing that can
// navigate), chosen over a hard `window.location` redirect specifically to keep a
// session expiry a normal in-SPA navigation.
//
// Single-subscriber by design: AuthProvider is the only consumer. A second call to
// onSessionExpired replaces the listener rather than stacking, which is fine as long
// as that invariant holds, this is not a general-purpose event emitter.
type Listener = () => void;

let listener: Listener | null = null;

export function onSessionExpired(fn: Listener): () => void {
  listener = fn;
  return () => {
    if (listener === fn) listener = null;
  };
}

export function notifySessionExpired(): void {
  listener?.();
}
