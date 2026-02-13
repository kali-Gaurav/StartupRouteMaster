/**
 * Telegram WebApp SDK integration: ready(), expand(), theme, MainButton.
 * Use inside Mini App routes; safe when not in Telegram (returns nulls/false).
 */

import { useEffect, useState, useCallback } from "react";

declare global {
  interface Window {
    Telegram?: {
      WebApp: {
        ready: () => void;
        expand: () => void;
        close: () => void;
        initData: string;
        initDataUnsafe: { user?: { id: number; first_name?: string; last_name?: string; username?: string } };
        themeParams: {
          bg_color?: string;
          text_color?: string;
          button_color?: string;
          button_text_color?: string;
          secondary_bg_color?: string;
        };
        colorScheme: "light" | "dark";
        MainButton: {
          show: () => void;
          hide: () => void;
          setText: (text: string) => void;
          onClick: (cb: () => void) => void;
          offClick: (cb: () => void) => void;
          showProgress: (leaveActive?: boolean) => void;
          hideProgress: () => void;
          enable: () => void;
          disable: () => void;
          isVisible: boolean;
        };
        BackButton: { show: () => void; hide: () => void; onClick: (cb: () => void) => void };
        sendData: (data: string) => void;
        openLink: (url: string) => void;
        openTelegramLink: (url: string) => void;
      };
    };
  }
}

export function useTelegramWebApp() {
  const [isReady, setReady] = useState(false);
  const webApp = typeof window !== "undefined" ? window.Telegram?.WebApp : undefined;

  useEffect(() => {
    if (!webApp) {
      setReady(true);
      return;
    }
    webApp.ready();
    webApp.expand();
    setReady(true);
  }, [webApp]);

  const applyTheme = useCallback(() => {
    if (!webApp?.themeParams) return;
    const root = document.documentElement;
    const tp = webApp.themeParams;
    if (tp.bg_color) root.style.setProperty("--tg-theme-bg-color", tp.bg_color);
    if (tp.text_color) root.style.setProperty("--tg-theme-text-color", tp.text_color);
    if (tp.button_color) root.style.setProperty("--tg-theme-button-color", tp.button_color);
    if (tp.button_text_color) root.style.setProperty("--tg-theme-button-text-color", tp.button_text_color);
    if (tp.secondary_bg_color) root.style.setProperty("--tg-theme-secondary-bg-color", tp.secondary_bg_color);
  }, [webApp]);

  useEffect(() => {
    applyTheme();
  }, [applyTheme, isReady]);

  const mainButton = webApp?.MainButton;
  const showMainButton = useCallback(
    (text: string, onClick: () => void) => {
      if (!mainButton) return () => {};
      mainButton.setText(text);
      mainButton.onClick(onClick);
      mainButton.show();
      return () => {
        mainButton.offClick(onClick);
        mainButton.hide();
      };
    },
    [mainButton]
  );

  const openSafeUrl = useCallback(
    (path: string) => {
      const base = import.meta.env.VITE_APP_BASE_URL || (typeof window !== "undefined" ? window.location.origin : "");
      const url = path.startsWith("http") ? path : `${base.replace(/\/$/, "")}${path.startsWith("/") ? path : `/${path}`}`;
      if (webApp?.openLink) webApp.openLink(url);
      else if (typeof window !== "undefined") window.open(url, "_blank");
    },
    [webApp]
  );

  return {
    webApp,
    isTelegram: !!webApp,
    isReady,
    initData: webApp?.initData ?? "",
    initDataUnsafe: webApp?.initDataUnsafe ?? {},
    themeParams: webApp?.themeParams ?? {},
    colorScheme: webApp?.colorScheme ?? "light",
    applyTheme,
    MainButton: mainButton,
    showMainButton,
    openSafeUrl,
    sendData: webApp?.sendData ? (data: string) => webApp.sendData(data) : () => {},
  };
}
