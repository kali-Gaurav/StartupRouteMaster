/**
 * useNoIndex — blocks Google from indexing a page.
 * Use on all private/authenticated pages.
 *
 * Usage: call at top of component, no arguments needed.
 *   useNoIndex();
 */
import { useEffect } from "react";

export function useNoIndex() {
  useEffect(() => {
    // Add noindex
    let robots = document.querySelector('meta[name="robots"]') as HTMLMetaElement;
    if (!robots) {
      robots = document.createElement("meta");
      robots.name = "robots";
      document.head.appendChild(robots);
    }
    const prev = robots.content;
    robots.content = "noindex, nofollow";

    // Remove canonical (private pages shouldn't canonicalize)
    const existingCanon = document.querySelector('link[rel="canonical"]');
    if (existingCanon) existingCanon.remove();

    return () => {
      robots.content = prev || "index, follow";
    };
  }, []);
}

/**
 * useCanonical — sets a canonical URL for the page.
 * Prevents duplicate content penalty from multiple URL params.
 */
export function useCanonical(path?: string) {
  useEffect(() => {
    const url = path
      ? `https://routemaster.vercel.app${path}`
      : `https://routemaster.vercel.app${window.location.pathname}`;

    let link = document.querySelector('link[rel="canonical"]') as HTMLLinkElement;
    if (!link) {
      link = document.createElement("link");
      link.rel = "canonical";
      document.head.appendChild(link);
    }
    link.href = url;

    return () => { link.remove(); };
  }, [path]);
}
