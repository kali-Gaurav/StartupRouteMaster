/**
 * usePageMeta — sets document title + meta description dynamically.
 * No external library needed — pure DOM manipulation.
 *
 * Usage:
 *   usePageMeta({
 *     title: "NDLS → BCT Train Routes",
 *     description: "Find all train routes from New Delhi to Mumbai Central..."
 *   });
 */
import { useEffect } from "react";

interface PageMeta {
  title?: string;
  description?: string;
  ogTitle?: string;
  ogDescription?: string;
}

const APP_NAME = "Route Master";

export function usePageMeta({ title, description, ogTitle, ogDescription }: PageMeta) {
  useEffect(() => {
    // Title
    const fullTitle = title ? `${title} | ${APP_NAME}` : `${APP_NAME} — Best Train Routes in India`;
    document.title = fullTitle;

    // Meta description
    if (description) {
      let meta = document.querySelector('meta[name="description"]') as HTMLMetaElement;
      if (!meta) {
        meta = document.createElement("meta");
        meta.name = "description";
        document.head.appendChild(meta);
      }
      meta.content = description;
    }

    // OG tags
    const ogTitleContent = ogTitle || fullTitle;
    const ogDescContent = ogDescription || description || "";

    const setOgMeta = (property: string, content: string) => {
      let meta = document.querySelector(`meta[property="${property}"]`) as HTMLMetaElement;
      if (!meta) {
        meta = document.createElement("meta");
        meta.setAttribute("property", property);
        document.head.appendChild(meta);
      }
      meta.content = content;
    };

    if (ogTitleContent) setOgMeta("og:title", ogTitleContent);
    if (ogDescContent) setOgMeta("og:description", ogDescContent);

    // Cleanup — restore defaults on unmount
    return () => {
      document.title = `${APP_NAME} — Find Best Train Routes in India | IRCTC Route Planner`;
    };
  }, [title, description, ogTitle, ogDescription]);
}
