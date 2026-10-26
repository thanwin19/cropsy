import { lazy, Suspense, type ComponentProps, type ComponentType, type ReactNode } from "react";
import { ClientOnly } from "@tanstack/react-router";

/**
 * Wrap a module that needs the browser (every Leaflet map) so it is imported and rendered on the client only.
 * Leaflet touches `window` the moment it is imported, so a plain import would break the server render.
 */
export function clientLazy<C extends ComponentType<any>>(load: () => Promise<{ default: C }>, fallback: ReactNode = null) {
  const Lazy = lazy(load);
  return function ClientLazy(props: ComponentProps<C>) {
    return (
      <ClientOnly fallback={fallback}>
        <Suspense fallback={fallback}>
          <Lazy {...(props as any)} />
        </Suspense>
      </ClientOnly>
    );
  };
}
